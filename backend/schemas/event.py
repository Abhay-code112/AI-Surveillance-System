"""Pydantic schemas for surveillance event records."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    """Schema for creating a new surveillance event in the database."""
    camera_id: str = Field("UPLOAD", description="Source camera identifier")
    activity: str = Field(..., description="Detected activity")
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_violent: bool = Field(False)
    violence_score: float = Field(0.0, ge=0.0, le=1.0)
    video_path: Optional[str] = Field(None, description="Path to uploaded video")
    screenshot_path: Optional[str] = Field(None, description="Path to saved screenshot")
    clip_path: Optional[str] = Field(None, description="Path to evidence video clip")
    alert_sent: bool = Field(False)
    mode: str = Field("video", description="Inference mode used")


class EventResponse(BaseModel):
    """Full event record returned from the database."""
    id: int
    timestamp: datetime
    camera_id: str
    activity: str
    confidence: float
    is_violent: bool
    violence_score: float
    video_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    clip_path: Optional[str] = None
    alert_sent: bool
    mode: str

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    """Paginated list of events."""
    total: int = Field(..., description="Total number of events matching the query")
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    events: list[EventResponse] = Field(default_factory=list)
