"""Inference service — wraps the ML pipeline for the FastAPI backend.

This module provides a clean interface between the FastAPI routes and the
SurveillanceEngine in ``backend.ml.inference_engine``.  It uses a
lazy-loaded singleton so the heavy model weights are loaded exactly once
and shared across all requests.

Key design decisions
--------------------
* **Clean imports**: The ML engine lives in ``backend/ml/`` as a proper
  Python package.  No sys.path hacking required.
* **Thread safety**: ``_load_engine()`` is guarded by a ``threading.Lock``
  to prevent double-loading if two requests arrive simultaneously before
  the engine is ready.
* **No global state mutation**: The service never modifies the original
  engine code; it only *reads* from it.
"""

import os

import uuid
import logging
import threading
from pathlib import Path
from typing import Optional

import cv2

logger = logging.getLogger(__name__)

# ── Path setup ────────────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR    = PROJECT_ROOT / "storage"
UPLOADS_DIR    = STORAGE_DIR / "uploads"
CLIPS_DIR      = STORAGE_DIR / "clips"
SCREENSHOTS_DIR = STORAGE_DIR / "screenshots"

# Ensure storage directories exist
for _dir in (UPLOADS_DIR, CLIPS_DIR, SCREENSHOTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ── Lazy singleton ────────────────────────────────────────────────
_engine = None
_engine_lock = threading.Lock()


def _load_engine():
    """Load the SurveillanceEngine exactly once (thread-safe)."""
    global _engine

    if _engine is not None:
        return _engine

    with _engine_lock:
        # Double-checked locking — another thread may have loaded it
        # while we were waiting for the lock.
        if _engine is not None:
            return _engine

        # Import the ml engine from the local package
        from backend.ml.inference_engine import SurveillanceEngine

        logger.info("Initialising SurveillanceEngine …")
        _engine = SurveillanceEngine()
        logger.info("SurveillanceEngine ready.")
        return _engine


def get_engine():
    """Public accessor — returns the shared SurveillanceEngine instance."""
    return _load_engine()


# ── Video helpers ─────────────────────────────────────────────────

def save_uploaded_video(file_bytes: bytes, original_filename: str) -> Path:
    """Persist an uploaded video to ``storage/uploads/``.

    Returns the full path to the saved file.  The filename is prefixed
    with a short UUID to avoid collisions.

    Parameters
    ----------
    file_bytes : bytes
        Raw file content from the upload.
    original_filename : str
        The original name the user gave the file (used for the extension).
    """
    ext = Path(original_filename).suffix or ".mp4"
    safe_name = f"{uuid.uuid4().hex[:12]}_{Path(original_filename).stem}{ext}"
    dest = UPLOADS_DIR / safe_name
    dest.write_bytes(file_bytes)
    logger.info("Saved uploaded video: %s (%d bytes)", dest, len(file_bytes))
    return dest


def save_screenshot(video_path: str, frame_index: Optional[int] = None) -> Optional[Path]:
    """Extract and save a single frame from *video_path* as a JPEG screenshot.

    Parameters
    ----------
    video_path : str
        Path to the video file.
    frame_index : int, optional
        Which frame to grab.  Defaults to the middle frame.

    Returns
    -------
    Path or None
        Path to the saved screenshot, or ``None`` if extraction failed.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0:
            cap.release()
            return None

        target = frame_index if frame_index is not None else total_frames // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        screenshot_name = f"{uuid.uuid4().hex[:12]}.jpg"
        dest = SCREENSHOTS_DIR / screenshot_name
        cv2.imwrite(str(dest), frame)
        logger.info("Saved screenshot: %s", dest)
        return dest

    except Exception:
        logger.exception("Failed to save screenshot from %s", video_path)
        return None


def save_evidence_clip(
    video_path: str,
    duration_seconds: float = 5.0,
) -> Optional[Path]:
    """Extract a short evidence clip from the middle of *video_path*.

    Saves a ~``duration_seconds`` segment centred on the video midpoint.
    This gives reviewers a quick look at what the model flagged.

    Parameters
    ----------
    video_path : str
        Path to the source video.
    duration_seconds : float
        How many seconds of footage to keep (default 5).

    Returns
    -------
    Path or None
        Path to the saved clip, or ``None`` on failure.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total <= 0:
            cap.release()
            return None

        # Calculate frame range for the clip
        clip_frames = int(fps * duration_seconds)
        mid = total // 2
        start = max(0, mid - clip_frames // 2)
        end = min(total - 1, start + clip_frames)

        clip_name = f"{uuid.uuid4().hex[:12]}_clip.mp4"
        dest = CLIPS_DIR / clip_name

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(str(dest), fourcc, fps, (w, h))

        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        for _ in range(end - start):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)

        writer.release()
        cap.release()
        logger.info("Saved evidence clip: %s (%d frames)", dest, end - start)
        return dest

    except Exception:
        logger.exception("Failed to save evidence clip from %s", video_path)
        return None


def run_video_prediction(video_path: str) -> dict:
    """Run the full inference pipeline on an uploaded video.

    This is the main entry point called by the ``/predict-video`` route.

    Steps
    -----
    1. Extract frames using the engine's built-in extractor.
    2. Run prediction in ``"video"`` mode (full pipeline).
    3. Reset the temporal smoothing buffer afterwards so that
       the next prediction starts fresh.

    Parameters
    ----------
    video_path : str
        Absolute path to the video file on disk.

    Returns
    -------
    dict
        Raw prediction dictionary from ``SurveillanceEngine.predict()``.

    Raises
    ------
    ValueError
        If no frames could be extracted from the video.
    RuntimeError
        If the inference engine encounters an internal error.
    """
    from backend.ml.inference_engine import extract_frames_from_video, CLIP_LEN

    engine = get_engine()
    engine.reset_smoothing()

    logger.info("Extracting frames from %s …", video_path)
    frames = extract_frames_from_video(str(video_path), CLIP_LEN)

    if not frames:
        raise ValueError(f"Could not extract any frames from {video_path}")

    logger.info("Running inference (mode=video, %d frames) …", len(frames))
    result = engine.predict(frames, mode="video")
    logger.info(
        "Prediction complete: activity=%s  confidence=%.2f  violent=%s",
        result["activity"],
        result["confidence"],
        result["is_violent"],
    )
    return result
