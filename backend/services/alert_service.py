"""Alert service — sends email and Telegram notifications (Phase 7).

This replaces the hardcoded credentials in the original ``Inference/alert.py``
with values loaded from ``.env`` via ``settings``.

Features
--------
* Email alerts via Gmail SMTP (SSL).
* Telegram alerts via the Bot API.
* Per-activity cooldown to avoid flooding.
* Every dispatched alert is logged to the ``alerts`` table.

Learning notes
--------------
* ``smtplib.SMTP_SSL`` opens an encrypted connection to Gmail on port 465.
* The Telegram Bot API is just a regular HTTP POST — no special SDK needed.
* The cooldown dict maps ``activity_name → last_alert_timestamp`` so that
  the same activity type can't trigger back-to-back alerts.
"""

import time
import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.database.models import Alert

logger = logging.getLogger(__name__)

# ── Per-activity cooldown tracking ────────────────────────────────
_last_alert_time: dict[str, float] = {}
_cooldown_lock = threading.Lock()


def _can_alert(activity: str) -> bool:
    """Check whether enough time has passed since the last alert for *activity*."""
    now = time.time()
    with _cooldown_lock:
        last = _last_alert_time.get(activity, 0.0)
        if now - last > settings.ALERT_COOLDOWN_SECONDS:
            _last_alert_time[activity] = now
            return True
    return False


# ── Email ─────────────────────────────────────────────────────────

def _send_email(activity: str, confidence: float, source: str) -> bool:
    """Send an alert email via Gmail SMTP-SSL.

    Returns ``True`` on success, ``False`` on failure.
    """
    if not settings.EMAIL_SENDER or not settings.EMAIL_PASSWORD:
        logger.warning("Email not configured — skipping.")
        return False

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receiver = settings.email_receiver

        subject = f"🚨 ALERT: {activity} Detected!"
        body = (
            f"🚨 SURVEILLANCE ALERT\n"
            f"{'─' * 40}\n"
            f"Activity Detected : {activity}\n"
            f"Confidence        : {confidence:.1%}\n"
            f"Source            : {source}\n"
            f"Time              : {timestamp}\n\n"
            f"This is an automated alert from your AI surveillance system.\n"
            f"Please review the footage immediately.\n"
        )

        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_SENDER
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(settings.EMAIL_SENDER, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_SENDER, receiver, msg.as_string())

        logger.info("Email alert sent to %s", receiver)
        return True

    except Exception:
        logger.exception("Email alert failed")
        return False


# ── Telegram ──────────────────────────────────────────────────────

def _send_telegram(activity: str, confidence: float, source: str) -> bool:
    """Send a Telegram bot message.

    Returns ``True`` on success, ``False`` on failure.
    """
    if not settings.TELEGRAM_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping.")
        return False

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"🚨 *SURVEILLANCE ALERT* 🚨\n\n"
            f"⚠ *{activity}* Detected!\n"
            f"📊 Confidence: {confidence:.1%}\n"
            f"📹 Source: {source}\n"
            f"🕐 Time: {timestamp}\n\n"
            f"Please review footage immediately!"
        )

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )

        if resp.status_code == 200:
            logger.info("Telegram alert sent.")
            return True
        else:
            logger.error("Telegram API error %d: %s", resp.status_code, resp.text)
            return False

    except Exception:
        logger.exception("Telegram alert failed")
        return False


# ── Public API ────────────────────────────────────────────────────

def send_alert(
    activity: str,
    confidence: float,
    source: str = "Video Upload",
    db: Optional[Session] = None,
    event_id: Optional[int] = None,
) -> bool:
    """Send alerts for a detected activity and log the result.

    Parameters
    ----------
    activity : str
        The detected activity name (e.g. "Fighting").
    confidence : float
        Model confidence for the detection.
    source : str
        Where the detection came from (e.g. "CCTV CAM-01").
    db : Session, optional
        If provided, an ``Alert`` record is persisted to the database.
    event_id : int, optional
        The related ``Event.id`` to link the alert to.

    Returns
    -------
    bool
        ``True`` if at least one channel (email or telegram) succeeded.
    """
    if not settings.ALERTS_ENABLED:
        logger.info("Alerts globally disabled — skipping.")
        return False

    if not _can_alert(activity):
        logger.info(
            "Alert cooldown active for '%s' (%ds) — skipping.",
            activity, settings.ALERT_COOLDOWN_SECONDS,
        )
        return False

    logger.info("Sending alerts for: %s (%.1f%%)", activity, confidence * 100)

    email_ok = _send_email(activity, confidence, source)
    telegram_ok = _send_telegram(activity, confidence, source)

    # Log to database
    if db is not None:
        alert_record = Alert(
            event_id=event_id,
            activity=activity,
            confidence=confidence,
            source=source,
            email_sent=email_ok,
            telegram_sent=telegram_ok,
        )
        db.add(alert_record)
        db.commit()
        logger.info("Alert #%d logged to database.", alert_record.id)

    return email_ok or telegram_ok
