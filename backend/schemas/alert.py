"""Pydantic schemas for the alert system (Phase 7)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    """A single alert record from the database."""

    id: int
    timestamp: datetime
    event_id: Optional[int] = None
    activity: str
    confidence: float
    source: str
    email_sent: bool
    telegram_sent: bool

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    total: int
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    alerts: list[AlertResponse] = Field(default_factory=list)


class AlertConfigResponse(BaseModel):
    """Current alert system configuration (read from settings)."""

    alerts_enabled: bool
    email_configured: bool
    telegram_configured: bool
    cooldown_seconds: int
