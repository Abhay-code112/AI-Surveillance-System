"""Service for managing async video-processing jobs (Phase 5).

This module handles the background worker logic. When a user uploads a video,
the API immediately returns a Job ID, and the heavy ML inference runs here
in a separate thread managed by FastAPI's BackgroundTasks.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.database.models import Job, Event
from backend.services.inference_service import (
    run_video_prediction,
    save_screenshot,
    save_evidence_clip,
)
from backend.services.alert_service import send_alert
from backend.schemas.prediction import PredictionResponse

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job(db: Session, video_path: str) -> Job:
    """Create a new pending job in the database."""
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, status="pending", video_path=video_path)
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created async job %s", job_id)
    return job


def get_job(db: Session, job_id: str) -> Optional[Job]:
    """Retrieve a job by ID."""
    return db.query(Job).filter(Job.id == job_id).first()


def process_video_task(job_id: str, db: Session) -> None:
    """The background task that runs the ML pipeline.

    Steps:
    1. Update job status to 'processing'
    2. Run inference on the video
    3. Save screenshot & clip
    4. Save Event to database
    5. Trigger alerts if necessary
    6. Update job status to 'completed'
    """
    job = get_job(db, job_id)
    if not job or job.video_path is None:
        logger.error("Job %s not found or missing video path", job_id)
        return

    try:
        # 1. Mark as processing
        job.status = "processing"
        db.commit()
        logger.info("Job %s: started processing %s", job_id, job.video_path)

        # 2. Run inference (this takes time)
        raw_result = run_video_prediction(job.video_path)
        
        is_violent = raw_result.get("is_violent", False)
        activity = raw_result.get("activity", "Unknown")
        confidence = raw_result.get("confidence", 0.0)
        violence_score = raw_result.get("violence_score", 0.0)

        # 3. Save evidence
        screenshot_path = save_screenshot(job.video_path)
        clip_path = None
        # Only save video clip if violent or highly suspicious to save disk space, 
        # or if configured to always save. For now, let's always save it to prove Phase 6 works.
        clip_path = save_evidence_clip(job.video_path, settings.CLIP_DURATION_SECONDS)

        # 4. Save Event to database
        event = Event(
            camera_id="UPLOAD_ASYNC",
            activity=activity,
            confidence=confidence,
            is_violent=is_violent,
            violence_score=violence_score,
            video_path=job.video_path,
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            clip_path=str(clip_path) if clip_path else None,
            mode="video",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info("Job %s: created Event #%d", job_id, event.id)

        # 5. Trigger Alerts (Phase 7)
        # Alert if violence is explicitly detected OR confidence is high for a violent activity
        alert_sent = False
        if is_violent or (violence_score > settings.VIOLENCE_THRESHOLD):
            alert_sent = send_alert(
                activity=activity,
                confidence=max(confidence, violence_score),
                source="Video Upload (Async)",
                db=db,
                event_id=event.id
            )
            
            # Update event to reflect alert status
            event.alert_sent = alert_sent
            db.commit()

        from backend.schemas.prediction import CrimeScore
        top3 = [
            CrimeScore(crime_type=name, confidence=conf)
            for name, conf in raw_result.get("top3", [])
        ]

        # Build response schema for the job result
        pred_response = PredictionResponse(
            event_id=event.id,
            timestamp=event.timestamp,
            is_violent=is_violent,
            activity=activity,
            confidence=confidence,
            violence_score=violence_score,
            top3=top3,
            all_scores=raw_result.get("all_scores", {}),
            alert_sent=alert_sent,
            mode="video"
        )

        # 6. Mark job as completed
        job.status = "completed"
        job.completed_at = _utcnow()
        job.event_id = event.id
        job.result_json = pred_response.model_dump_json()
        db.commit()
        logger.info("Job %s: completed successfully", job_id)

    except Exception as e:
        logger.exception("Job %s: failed during processing", job_id)
        job.status = "failed"
        job.completed_at = _utcnow()
        job.error = str(e)
        db.commit()
