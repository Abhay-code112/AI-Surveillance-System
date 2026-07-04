"""Events route — query and manage surveillance event history.

Endpoints
---------
GET  /api/events       — list events (paginated, filterable)
GET  /api/events/{id}  — get a single event by ID

Learning notes
--------------
* ``Query(...)`` lets you define optional URL query parameters with
  defaults and validation.  For example ``?page=2&per_page=10``.
* We use ``offset`` and ``limit`` in the SQL query to implement
  pagination — the same pattern used by every production API.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.session import get_db
from backend.database.models import Event
from backend.schemas.event import EventResponse, EventListResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events", response_model=EventListResponse)
def list_events(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    is_violent: Optional[bool] = Query(None, description="Filter by violence flag"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    db: Session = Depends(get_db),
):
    """Retrieve a paginated list of surveillance events.

    **Query parameters:**
    - ``page`` — which page to return (default: 1)
    - ``per_page`` — how many results per page (default: 20, max: 100)
    - ``is_violent`` — optional filter: ``true`` or ``false``
    - ``camera_id`` — optional filter: e.g. ``CAM-01``

    Events are returned in reverse chronological order (newest first).
    """
    query = db.query(Event)

    # Apply optional filters
    if is_violent is not None:
        query = query.filter(Event.is_violent == is_violent)
    if camera_id is not None:
        query = query.filter(Event.camera_id == camera_id)

    # Get total count (before pagination)
    total = query.count()

    # Apply pagination — newest events first
    events = (
        query
        .order_by(desc(Event.timestamp))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    logger.info(
        "Listed events: page=%d  per_page=%d  total=%d  returned=%d",
        page, per_page, total, len(events),
    )

    return EventListResponse(
        total=total,
        page=page,
        per_page=per_page,
        events=[EventResponse.model_validate(e) for e in events],
    )


@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve a single event by its ID.

    Returns 404 if the event does not exist.
    """
    event = db.query(Event).filter(Event.id == event_id).first()

    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found.")

    return EventResponse.model_validate(event)
