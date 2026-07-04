"""Alerts route — view alert history and configuration (Phase 7).

Endpoints
---------
GET /api/alerts         — List past alerts (paginated)
GET /api/alerts/config  — Get current alert system configuration
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.session import get_db
from backend.database.models import Alert
from backend.schemas.alert import AlertListResponse, AlertResponse, AlertConfigResponse
from backend.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    activity: Optional[str] = Query(None, description="Filter by activity name"),
    db: Session = Depends(get_db),
):
    """List historical alert dispatches."""
    query = db.query(Alert)

    if activity:
        query = query.filter(Alert.activity == activity)

    total = query.count()
    alerts = (
        query
        .order_by(desc(Alert.timestamp))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return AlertListResponse(
        total=total,
        page=page,
        per_page=per_page,
        alerts=[AlertResponse.model_validate(a) for a in alerts],
    )


@router.get("/alerts/config", response_model=AlertConfigResponse)
def get_alert_config():
    """Check if the alert system is configured properly.
    
    This does NOT expose passwords or tokens, it just returns booleans
    indicating if the credentials exist in the .env file.
    """
    return AlertConfigResponse(
        alerts_enabled=settings.ALERTS_ENABLED,
        email_configured=bool(settings.EMAIL_SENDER and settings.EMAIL_PASSWORD),
        telegram_configured=bool(settings.TELEGRAM_TOKEN and settings.TELEGRAM_CHAT_ID),
        cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS,
    )
