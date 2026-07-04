"""SQLAlchemy ORM models for the surveillance database.

Tables
------
* **events** — one row per inference result (prediction log).
* **jobs**   — one row per async video-processing job.
* **alerts** — one row per alert dispatched (email / telegram).
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp for column defaults."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class User(Base):
    """Platform user for authentication (Phase 11).

    Passwords are stored as bcrypt hashes — never in plain text.
    The ``role`` column supports simple RBAC: 'admin' or 'viewer'.
    """
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String(50), unique=True, nullable=False, index=True)
    email      = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role       = Column(String(20), default="viewer", nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    connection_url = Column(String)  # RTSP URL or "0" for webcam
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    """A single surveillance event (one prediction result).

    Every time the system runs inference on a video or live clip,
    the result is stored as an Event for audit and analytics.
    """
    __tablename__ = "events"

    id              = Column(Integer, primary_key=True, index=True)
    timestamp       = Column(DateTime, default=_utcnow, nullable=False)
    camera_id       = Column(String(50), default="UPLOAD", nullable=False, index=True)
    activity        = Column(String(100), nullable=False)
    confidence      = Column(Float, nullable=False)
    is_violent      = Column(Boolean, default=False, nullable=False)
    violence_score  = Column(Float, default=0.0, nullable=False)
    video_path      = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    clip_path       = Column(Text, nullable=True)       # Phase 6: evidence clip
    alert_sent      = Column(Boolean, default=False, nullable=False)
    mode            = Column(String(20), default="video", nullable=False)

    # Relationships
    alerts = relationship("Alert", back_populates="event", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Event id={self.id} activity='{self.activity}' "
            f"confidence={self.confidence:.2f} violent={self.is_violent}>"
        )


class Job(Base):
    """An async video-processing job (Phase 5).

    When a user uploads a video to the async endpoint, a Job is created
    immediately with ``status='pending'``.  A background worker picks it
    up, sets ``status='processing'``, runs inference, and finally sets
    ``status='completed'`` (or ``'failed'``).

    The frontend can poll ``GET /api/jobs/{id}`` to check progress.
    """
    __tablename__ = "jobs"

    id           = Column(String(36), primary_key=True)         # UUID4
    status       = Column(String(20), default="pending", nullable=False, index=True)
    video_path   = Column(Text, nullable=True)
    result_json  = Column(Text, nullable=True)                  # JSON-encoded prediction
    error        = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    event_id     = Column(Integer, ForeignKey("events.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<Job id={self.id[:8]}… status={self.status}>"


class Alert(Base):
    """Record of a dispatched alert (Phase 7).

    Tracks every email and Telegram notification sent by the system,
    including whether delivery succeeded.
    """
    __tablename__ = "alerts"

    id            = Column(Integer, primary_key=True, index=True)
    timestamp     = Column(DateTime, default=_utcnow, nullable=False)
    event_id      = Column(Integer, ForeignKey("events.id"), nullable=True)
    activity      = Column(String(100), nullable=False)
    confidence    = Column(Float, nullable=False)
    source        = Column(String(50), default="Video Upload", nullable=False)
    email_sent    = Column(Boolean, default=False, nullable=False)
    telegram_sent = Column(Boolean, default=False, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="alerts")

    def __repr__(self) -> str:
        return (
            f"<Alert id={self.id} activity='{self.activity}' "
            f"email={self.email_sent} telegram={self.telegram_sent}>"
        )
