"""Pydantic schemas for async video-processing jobs (Phase 5).

The async flow:
    1. Client sends POST /api/jobs/predict-video  →  gets back a JobResponse
    2. Server processes in the background
    3. Client polls GET /api/jobs/{id}            →  gets updated JobResponse
    4. When status == "completed", the result field contains the prediction
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.schemas.prediction import PredictionResponse


class JobResponse(BaseModel):
    """Current state of an async processing job."""

    id: str = Field(..., description="Unique job identifier (UUID)")
    status: str = Field(
        ...,
        description="Job status: pending, processing, completed, or failed",
    )
    created_at: datetime
    completed_at: Optional[datetime] = None
    video_path: Optional[str] = None
    error: Optional[str] = Field(None, description="Error message if status is 'failed'")
    event_id: Optional[int] = Field(None, description="Linked event ID once completed")
    result: Optional[PredictionResponse] = Field(
        None, description="Prediction result (populated when status == 'completed')",
    )

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    total: int
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    jobs: list[JobResponse] = Field(default_factory=list)
