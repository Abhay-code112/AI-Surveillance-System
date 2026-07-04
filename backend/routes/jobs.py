"""Jobs route — manage async video-processing jobs (Phase 5).

Endpoints
---------
POST /api/jobs/predict-video  — Upload a video and start a background job
GET  /api/jobs/{id}           — Poll job status
GET  /api/jobs                — List recent jobs
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.services.auth_service import get_current_user, require_admin, rate_limit
from backend.database.models import User

from backend.database.session import get_db
from backend.database.session import SessionLocal
from backend.database.models import Job
from backend.schemas.job import JobResponse, JobListResponse
from backend.services.inference_service import save_uploaded_video
from backend.services.job_service import create_job, get_job, process_video_task

logger = logging.getLogger(__name__)
router = APIRouter()


def run_background_task(job_id: str):
    """Wrapper to run the task with a fresh database session.
    
    FastAPI BackgroundTasks run after the response is sent, so the original
    Dependency-injected DB session will be closed. We need a new one.
    """
    db = SessionLocal()
    try:
        process_video_task(job_id, db)
    finally:
        db.close()


@router.post("/jobs/predict-video", response_model=JobResponse, status_code=202, dependencies=[Depends(rate_limit)])
async def create_predict_job(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Upload a video for asynchronous ML inference.
    
    Returns a Job ID immediately (HTTP 202 Accepted).
    Use ``GET /api/jobs/{id}`` to poll for completion.
    """
    # 1. Read file into memory (FastAPI handles chunks for large files via UploadFile)
    file_bytes = await video.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # 2. Save video to disk
    original_filename = video.filename or "upload.mp4"
    saved_path = save_uploaded_video(file_bytes, original_filename)

    # 3. Create job in database
    job = create_job(db, str(saved_path))

    # 4. Schedule background task
    background_tasks.add_task(run_background_task, job.id)

    # 5. Return job info immediately
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the current status of a background job.
    
    When status is 'completed', the ``result`` field will contain the full
    prediction response.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
        
    # Build response, dynamically parsing the JSON result if it exists
    resp_dict = {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "video_path": job.video_path,
        "error": job.error,
        "event_id": job.event_id,
    }
    
    if job.result_json:
        import json
        resp_dict["result"] = json.loads(job.result_json)
        
    return resp_dict


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    status: Optional[str] = Query(None, description="Filter by job status (e.g. pending, completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent async processing jobs."""
    query = db.query(Job)

    if status:
        query = query.filter(Job.status == status)

    total = query.count()
    jobs = (
        query
        .order_by(desc(Job.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Build response list
    job_responses = []
    for job in jobs:
        resp_dict = {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "video_path": job.video_path,
            "error": job.error,
            "event_id": job.event_id,
        }
        if job.result_json:
            import json
            resp_dict["result"] = json.loads(job.result_json)
        job_responses.append(resp_dict)

    return JobListResponse(
        total=total,
        page=page,
        per_page=per_page,
        jobs=job_responses,
    )
