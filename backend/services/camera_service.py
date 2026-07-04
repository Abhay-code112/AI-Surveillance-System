"""Camera stream service — manages live video feeds (Phase 8).

This module runs a background thread per registered camera.  Each thread:
1. Opens the video source via ``cv2.VideoCapture`` (RTSP, HTTP, webcam, or file).
2. Buffers the most recent 16 frames in a ring-buffer.
3. Every ``INFERENCE_INTERVAL`` seconds, runs the inference engine in ``live`` mode.
4. If violence is detected, saves a screenshot, logs an Event, and dispatches
   alerts (email / Telegram) through the existing alert service.

Learning notes
--------------
* ``threading.Event`` is used for stop signals instead of a plain bool — it is
  thread-safe by design and also allows ``wait()`` which is cleaner than
  ``time.sleep()`` loops.
* Each thread creates its **own** DB session (``SessionLocal()``) because
  SQLAlchemy sessions are NOT thread-safe.
* The ``sync_active_cameras()`` function is called on startup and whenever
  a camera is created / updated / deleted via the API.
"""

import uuid
import time
import threading
import logging
from collections import deque
from pathlib import Path
from typing import Dict

import cv2

from backend.database.session import SessionLocal
from backend.database.models import Camera, Event
from backend.services.inference_service import get_engine, SCREENSHOTS_DIR

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────
INFERENCE_INTERVAL = 3.0       # seconds between live predictions
FRAME_READ_DELAY   = 0.1       # ~10 FPS capture rate
RECONNECT_DELAY    = 5.0       # seconds before retrying a dead stream
CLIP_LEN           = 16        # frames per inference batch

# ── Active thread registry ────────────────────────────────────────
_camera_threads: Dict[int, threading.Thread] = {}
_stop_events:    Dict[int, threading.Event]  = {}


_latest_frames: Dict[int, bytes] = {}

# ──────────────────────────────────────────────────────────────────
#  Screenshot helper (saves a raw OpenCV frame directly)
# ──────────────────────────────────────────────────────────────────

def _save_frame_screenshot(frame) -> str | None:
    """Save an OpenCV frame directly as a JPEG screenshot."""
    try:
        name = f"{uuid.uuid4().hex[:12]}.jpg"
        dest = SCREENSHOTS_DIR / name
        cv2.imwrite(str(dest), frame)
        logger.info("Saved live screenshot: %s", dest)
        return str(dest)
    except Exception:
        logger.exception("Failed to save live screenshot")
        return None


# ──────────────────────────────────────────────────────────────────
#  Per-camera background worker
# ──────────────────────────────────────────────────────────────────

import queue

def _process_camera_stream(
    camera_id: int,
    connection_url: str,
    name: str,
    stop_event: threading.Event,
) -> None:
    """Background thread: read frames → buffer → infer → log events."""
    logger.info(
        "Camera %d (%s): stream started from %s", camera_id, name, connection_url
    )

    src = 0 if connection_url == "0" else connection_url
    
    # Thread-safe queue containing only the latest frame
    frame_q = queue.Queue(maxsize=1)
    
    def _grabber():
        cap = cv2.VideoCapture(src)
        while not stop_event.is_set():
            if not cap.isOpened():
                cap = cv2.VideoCapture(src)
                if not cap.isOpened():
                    stop_event.wait(RECONNECT_DELAY)
                    continue

            ret, frame = cap.read()
            if not ret:
                logger.warning("Camera %d: stream lost — reconnecting...", camera_id)
                cap.release()
                stop_event.wait(RECONNECT_DELAY)
                continue
            
            # Drain the queue to keep only the absolute latest frame (no lag)
            if frame_q.full():
                try:
                    frame_q.get_nowait()
                except queue.Empty:
                    pass
            frame_q.put(frame)
        cap.release()

    grabber_thread = threading.Thread(target=_grabber, daemon=True)
    grabber_thread.start()

    frames_buffer: deque = deque(maxlen=CLIP_LEN)
    last_inference = 0.0

    try:
        while not stop_event.is_set():
            try:
                frame = frame_q.get(timeout=FRAME_READ_DELAY)
            except queue.Empty:
                continue

            frames_buffer.append(frame)
            
            # Store latest frame for MJPEG streaming
            ret_jpg, buffer = cv2.imencode('.jpg', frame)
            if ret_jpg:
                _latest_frames[camera_id] = buffer.tobytes()

            now = time.time()
            if len(frames_buffer) == CLIP_LEN and (now - last_inference) >= INFERENCE_INTERVAL:
                last_inference = now
                _run_live_inference(
                    camera_id, name, list(frames_buffer), frame
                )

            # Pace the inference loop assembly (~10 FPS)
            if stop_event.wait(FRAME_READ_DELAY):
                break

    finally:
        logger.info("Camera %d (%s): stream stopped.", camera_id, name)



def _run_live_inference(
    camera_id: int,
    camera_name: str,
    frames: list,
    last_frame,
) -> None:
    """Run a single live-mode prediction and persist results if violent."""
    try:
        engine = get_engine()
        result = engine.predict(frames, mode="live")
    except Exception:
        logger.exception("Camera %d: inference error", camera_id)
        return

    if not result.get("is_violent", False):
        return  # normal activity — nothing to log

    logger.warning(
        "🚨 Camera %d (%s): %s detected (confidence=%.2f)",
        camera_id, camera_name, result["activity"], result["confidence"],
    )

    screenshot_path = _save_frame_screenshot(last_frame)

    # Persist event
    db = SessionLocal()
    try:
        event = Event(
            camera_id=f"CAM_{camera_id}",
            activity=result["activity"],
            confidence=result["confidence"],
            is_violent=True,
            violence_score=result.get("v_score", 0.0),
            screenshot_path=screenshot_path,
            alert_sent=False,
            mode="live",
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Dispatch alerts through the existing alert service
        if result.get("send_alert", False):
            from backend.services.alert_service import send_alert

            alert_ok = send_alert(
                activity=result["activity"],
                confidence=result["confidence"],
                source=f"Camera {camera_id} ({camera_name})",
                db=db,
                event_id=event.id,
            )
            if alert_ok:
                event.alert_sent = True
                db.commit()

        # Push to WebSocket clients (Phase 9)
        try:
            from backend.routes.ws import manager as ws_manager

            ws_manager.broadcast({
                "type": "new_event",
                "event": {
                    "id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "camera_id": event.camera_id,
                    "activity": event.activity,
                    "confidence": round(event.confidence, 3),
                    "is_violent": event.is_violent,
                    "violence_score": round(event.violence_score, 3),
                    "screenshot_path": event.screenshot_path,
                    "alert_sent": event.alert_sent,
                    "mode": event.mode,
                },
            })
        except Exception:
            logger.debug("WebSocket broadcast skipped (no clients)")
    except Exception:
        logger.exception("Camera %d: failed to persist event", camera_id)
        db.rollback()
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────
#  Public API — start / stop / sync
# ──────────────────────────────────────────────────────────────────

def start_camera(camera_id: int, connection_url: str, name: str) -> None:
    """Launch a background thread for a single camera."""
    if camera_id in _camera_threads and _camera_threads[camera_id].is_alive():
        logger.info("Camera %d is already running.", camera_id)
        return

    stop_event = threading.Event()
    _stop_events[camera_id] = stop_event

    thread = threading.Thread(
        target=_process_camera_stream,
        args=(camera_id, connection_url, name, stop_event),
        daemon=True,
        name=f"cam-{camera_id}",
    )
    _camera_threads[camera_id] = thread
    thread.start()


def stop_camera(camera_id: int) -> None:
    """Signal a camera thread to stop gracefully."""
    evt = _stop_events.get(camera_id)
    if evt:
        evt.set()
        logger.info("Camera %d: stop requested.", camera_id)


def get_camera_status() -> dict:
    """Return a summary of all camera thread states (useful for /health)."""
    return {
        cam_id: {
            "alive": thread.is_alive(),
            "stopped": _stop_events.get(cam_id, threading.Event()).is_set(),
        }
        for cam_id, thread in _camera_threads.items()
    }


def sync_active_cameras() -> None:
    """Reconcile running threads with the database ``cameras`` table.

    * Starts threads for active cameras that are not yet running.
    * Stops threads for cameras that have been deactivated or deleted.
    """
    db = SessionLocal()
    try:
        active_cams = db.query(Camera).filter(Camera.is_active.is_(True)).all()
        active_ids = {cam.id for cam in active_cams}

        # Start new / restarted cameras
        for cam in active_cams:
            if cam.id not in _camera_threads or not _camera_threads[cam.id].is_alive():
                start_camera(cam.id, cam.connection_url, cam.name)

        # Stop cameras that are no longer active
        for cam_id in list(_camera_threads.keys()):
            if cam_id not in active_ids:
                stop_camera(cam_id)
    finally:
        db.close()


def get_video_stream(camera_id: int):
    """Generator function that yields JPEG frames for MJPEG streaming."""
    while True:
        frame_bytes = _latest_frames.get(camera_id)
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.1) # yield at roughly 10fps
