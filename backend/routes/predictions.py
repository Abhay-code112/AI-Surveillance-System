"""Prediction route — handles video upload and inference.

Endpoint
--------
POST /api/predict-video
    Accepts a video file, runs the full surveillance pipeline, logs the
    result as an Event in the database, and returns a structured JSON
    response.

Learning notes
--------------
* ``UploadFile`` is FastAPI's way of handling file uploads.  It gives you
  an async-friendly file object with ``.read()``, ``.filename``, etc.
* ``Depends(get_db)`` is *dependency injection* — FastAPI calls ``get_db()``
  for each request and passes the resulting database session to your
  function.  After the request finishes, the session is automatically
  closed.
* We use ``BackgroundTasks`` for the screenshot saving so the user gets
  their response immediately without waiting for disk I/O.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.database.models import Event
from backend.schemas.prediction import PredictionResponse, CrimeScore
from backend.services.inference_service import (
    save_uploaded_video,
    save_screenshot,
    run_video_prediction,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Maximum upload size: 500 MB
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

# Allowed video MIME types
ALLOWED_TYPES = {
    "video/mp4", "video/avi", "video/x-msvideo",
    "video/quicktime", "video/x-matroska", "video/webm",
}


@router.post("/predict-video", response_model=PredictionResponse)
async def predict_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="Video file to analyse"),
    db: Session = Depends(get_db),
):
    """Upload a video and get a violence/activity prediction.

    **What happens behind the scenes:**

    1. The uploaded file is validated (size & type checks).
    2. The file is saved to ``storage/uploads/``.
    3. The AI inference engine extracts frames and runs the full
       multi-stage pipeline (violence detection → activity classification
       → crime type classification).
    4. A screenshot is saved from the video's middle frame.
    5. The result is logged to the ``events`` table in SQLite.
    6. A structured JSON response is returned.

    **Example response:**
    ```json
    {
        "event_id": 1,
        "is_violent": true,
        "activity": "Fighting",
        "confidence": 0.94,
        "violence_score": 0.87,
        "alert_sent": false,
        "mode": "video"
    }
    ```
    """
    # ── 1. Validate upload ────────────────────────────────────────
    if video.content_type and video.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{video.content_type}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    file_bytes = await video.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). "
                   f"Maximum is {MAX_UPLOAD_BYTES / 1024 / 1024:.0f} MB.",
        )

    # ── 2. Save the uploaded file ─────────────────────────────────
    try:
        video_path = save_uploaded_video(file_bytes, video.filename or "upload.mp4")
    except Exception as exc:
        logger.exception("Failed to save uploaded video")
        raise HTTPException(status_code=500, detail=f"Could not save video: {exc}")

    # ── 3. Run inference ──────────────────────────────────────────
    try:
        result = run_video_prediction(str(video_path))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}")

    # ── 4. Save screenshot in the background ──────────────────────
    screenshot_path = None
    try:
        screenshot_result = save_screenshot(str(video_path))
        if screenshot_result is not None:
            screenshot_path = str(screenshot_result)
    except Exception:
        logger.warning("Screenshot saving failed — continuing without it")

    # ── 5. Log event to database ──────────────────────────────────
    event = Event(
        camera_id="UPLOAD",
        activity=result["activity"],
        confidence=result["confidence"],
        is_violent=result["is_violent"],
        violence_score=result.get("v_score", 0.0),
        video_path=str(video_path),
        screenshot_path=screenshot_path,
        alert_sent=result.get("send_alert", False),
        mode="video",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info("Event #%d logged to database.", event.id)

    # ── 6. Build response ─────────────────────────────────────────
    top3 = [
        CrimeScore(crime_type=name, confidence=conf)
        for name, conf in result.get("top3", [])
    ]

    return PredictionResponse(
        event_id=event.id,
        timestamp=event.timestamp,
        is_violent=result["is_violent"],
        activity=result["activity"],
        confidence=result["confidence"],
        violence_score=result.get("v_score", 0.0),
        top3=top3,
        all_scores=result.get("all_scores", {}),
        alert_sent=result.get("send_alert", False),
        mode="video",
    )
