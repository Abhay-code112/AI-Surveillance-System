"""Pydantic schemas for video prediction requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CrimeScore(BaseModel):
    """Individual crime type score from binary classifiers."""
    crime_type: str = Field(..., description="Type of crime detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")


class PredictionResponse(BaseModel):
    """Response from a video prediction request."""
    event_id: int = Field(..., description="Database event ID for this prediction")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_violent: bool = Field(..., description="Whether violence was detected")
    activity: str = Field(..., description="Predicted activity label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence")
    violence_score: float = Field(..., ge=0.0, le=1.0, description="Smoothed violence probability")
    top3: list[CrimeScore] = Field(default_factory=list, description="Top 3 activity predictions")
    all_scores: dict[str, float] = Field(default_factory=dict, description="All crime classifier scores")
    alert_sent: bool = Field(False, description="Whether an alert was triggered")
    mode: str = Field("video", description="Inference mode: 'live' or 'video'")


class PredictionSummary(BaseModel):
    """Lightweight prediction result for list views."""
    event_id: int
    timestamp: datetime
    activity: str
    confidence: float
    is_violent: bool
    alert_sent: bool
