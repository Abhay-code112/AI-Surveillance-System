"""Analytics route — dashboard statistics and reporting (Phase 10).

Provides aggregated data for the frontend dashboard:
* Total event counts by activity, time range, and camera.
* Violence trend over time (hourly/daily buckets).
* Camera health summary (active streams, last event).
* System-wide statistics for the admin panel.

Learning notes
--------------
* ``func.count()``, ``func.avg()``, ``func.date()`` are SQLAlchemy
  "column functions" — they generate SQL like ``COUNT(*)``, ``AVG(confidence)``.
* ``group_by()`` works just like SQL GROUP BY and is essential for
  aggregation queries.
* We return plain dicts rather than Pydantic models here because the
  analytics shapes are flexible and change as we add new dashboards.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, desc
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.database.models import Event, Alert, Camera, Job
from backend.services.camera_service import get_camera_status

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────────
#  GET /api/analytics/summary
# ──────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """High-level platform statistics for the dashboard header.

    Returns counts for total events, violent events, alerts sent,
    cameras registered, and the most recent event timestamp.
    """
    total_events = db.query(func.count(Event.id)).scalar() or 0
    violent_events = (
        db.query(func.count(Event.id))
        .filter(Event.is_violent.is_(True))
        .scalar() or 0
    )
    total_alerts = db.query(func.count(Alert.id)).scalar() or 0
    total_cameras = db.query(func.count(Camera.id)).scalar() or 0
    active_cameras = (
        db.query(func.count(Camera.id))
        .filter(Camera.is_active.is_(True))
        .scalar() or 0
    )
    total_jobs = db.query(func.count(Job.id)).scalar() or 0

    last_event = (
        db.query(Event.timestamp)
        .order_by(desc(Event.timestamp))
        .first()
    )

    return {
        "total_events": total_events,
        "violent_events": violent_events,
        "normal_events": total_events - violent_events,
        "total_alerts": total_alerts,
        "total_cameras": total_cameras,
        "active_cameras": active_cameras,
        "total_jobs": total_jobs,
        "last_event_at": last_event[0].isoformat() if last_event else None,
        "camera_threads": get_camera_status(),
    }


# ──────────────────────────────────────────────────────────────────
#  GET /api/analytics/activity-breakdown
# ──────────────────────────────────────────────────────────────────

@router.get("/activity-breakdown")
def get_activity_breakdown(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
    db: Session = Depends(get_db),
):
    """Count of events grouped by activity type within the last *hours*.

    Useful for pie/donut charts on the dashboard.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = (
        db.query(
            Event.activity,
            func.count(Event.id).label("count"),
            func.avg(Event.confidence).label("avg_confidence"),
        )
        .filter(Event.timestamp >= cutoff)
        .group_by(Event.activity)
        .order_by(desc("count"))
        .all()
    )

    return {
        "window_hours": hours,
        "breakdown": [
            {
                "activity": row.activity,
                "count": row.count,
                "avg_confidence": round(float(row.avg_confidence), 3),
            }
            for row in rows
        ],
    }


# ──────────────────────────────────────────────────────────────────
#  GET /api/analytics/timeline
# ──────────────────────────────────────────────────────────────────

@router.get("/timeline")
def get_event_timeline(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
    bucket: str = Query("hour", description="Bucket size: 'hour' or 'day'"),
    db: Session = Depends(get_db),
):
    """Event counts bucketed by hour or day — drives line/bar charts.

    Returns separate counts for violent and normal events so the
    frontend can render stacked or grouped visualisations.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # SQLite date functions
    if bucket == "day":
        time_bucket = func.date(Event.timestamp)
    else:
        # SQLite: strftime('%Y-%m-%d %H:00', timestamp)
        time_bucket = func.strftime("%Y-%m-%d %H:00", Event.timestamp)

    rows = (
        db.query(
            time_bucket.label("bucket"),
            func.count(Event.id).label("total"),
            func.sum(case((Event.is_violent.is_(True), 1), else_=0)).label("violent"),
            func.sum(case((Event.is_violent.is_(False), 1), else_=0)).label("normal"),
        )
        .filter(Event.timestamp >= cutoff)
        .group_by("bucket")
        .order_by("bucket")
        .all()
    )

    return {
        "window_hours": hours,
        "bucket_size": bucket,
        "data": [
            {
                "time": row.bucket,
                "total": row.total,
                "violent": int(row.violent or 0),
                "normal": int(row.normal or 0),
            }
            for row in rows
        ],
    }


# ──────────────────────────────────────────────────────────────────
#  GET /api/analytics/cameras
# ──────────────────────────────────────────────────────────────────

@router.get("/cameras")
def get_camera_analytics(db: Session = Depends(get_db)):
    """Per-camera event counts and last activity — for the camera grid."""
    cameras = db.query(Camera).all()
    thread_status = get_camera_status()

    result = []
    for cam in cameras:
        cam_events = (
            db.query(func.count(Event.id))
            .filter(Event.camera_id == f"CAM_{cam.id}")
            .scalar() or 0
        )
        cam_violent = (
            db.query(func.count(Event.id))
            .filter(Event.camera_id == f"CAM_{cam.id}", Event.is_violent.is_(True))
            .scalar() or 0
        )
        last = (
            db.query(Event)
            .filter(Event.camera_id == f"CAM_{cam.id}")
            .order_by(desc(Event.timestamp))
            .first()
        )

        status = thread_status.get(cam.id, {})

        result.append({
            "id": cam.id,
            "name": cam.name,
            "location": cam.location,
            "is_active": cam.is_active,
            "connection_url": cam.connection_url,
            "total_events": cam_events,
            "violent_events": cam_violent,
            "last_activity": last.activity if last else None,
            "last_event_at": last.timestamp.isoformat() if last else None,
            "thread_alive": status.get("alive", False),
        })

    return {"cameras": result}


# ──────────────────────────────────────────────────────────────────
#  GET /api/analytics/recent-alerts
# ──────────────────────────────────────────────────────────────────

@router.get("/recent-alerts")
def get_recent_alerts(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """The most recent alerts for the live dashboard feed."""
    alerts = (
        db.query(Alert)
        .order_by(desc(Alert.timestamp))
        .limit(limit)
        .all()
    )
    return {
        "alerts": [
            {
                "id": a.id,
                "timestamp": a.timestamp.isoformat(),
                "activity": a.activity,
                "confidence": round(a.confidence, 3),
                "source": a.source,
                "email_sent": a.email_sent,
                "telegram_sent": a.telegram_sent,
                "event_id": a.event_id,
            }
            for a in alerts
        ]
    }
