"""WebSocket route — real-time event push to connected dashboards (Phase 9).

Why WebSockets?
--------------
Polling ``GET /api/events`` every second is wasteful.  WebSockets let the
server *push* new events to every connected browser tab the instant they
happen.  This is what makes a surveillance dashboard feel "live".

How it works
------------
1. The frontend opens a WebSocket connection to ``/ws/events``.
2. The server adds the connection to a ``ConnectionManager``.
3. Whenever a new Event is persisted (from a camera stream or async job),
   any code can call ``manager.broadcast(event_dict)`` to push it to all
   connected clients.
4. Disconnected clients are automatically cleaned up.

Learning notes
--------------
* ``WebSocket`` in FastAPI is almost identical to a regular endpoint — you
  accept the connection with ``await ws.accept()`` and then loop to
  receive/send messages.
* We use an ``asyncio.Queue`` per client so the broadcast is non-blocking.
* The ``ConnectionManager`` is a singleton module-level instance that can
  be imported from anywhere in the backend.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events.

    Thread-safety: ``broadcast()`` can be called from any thread — it uses
    ``asyncio.run_coroutine_threadsafe`` to safely schedule the send on
    the event loop.
    """

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        self._loop = asyncio.get_event_loop()
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def _send_to_all(self, message: dict) -> None:
        """Send JSON to every connected client, removing dead ones."""
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def broadcast(self, message: dict) -> None:
        """Broadcast from *any* thread (sync-safe entry point).

        Camera threads call this after persisting an Event.
        """
        if not self._connections:
            return

        loop = self._loop
        if loop is None or loop.is_closed():
            return

        try:
            asyncio.run_coroutine_threadsafe(self._send_to_all(message), loop)
        except RuntimeError:
            pass  # loop already stopped — server is shutting down


# Module-level singleton — import from anywhere
manager = ConnectionManager()


@router.websocket("/events")
async def ws_events(ws: WebSocket):
    """WebSocket endpoint for real-time event streaming.

    **Connect**: ``ws://127.0.0.1:8000/ws/events``

    Once connected, the server pushes JSON messages whenever a new
    surveillance event is created::

        {
            "type": "new_event",
            "event": {
                "id": 42,
                "activity": "Fighting",
                "confidence": 0.91,
                "is_violent": true,
                "camera_id": "CAM_1",
                "timestamp": "2026-07-04T10:30:00",
                "mode": "live"
            }
        }
    """
    await manager.connect(ws)
    try:
        while True:
            # Keep the connection alive.  We listen for pings or
            # client-sent messages (ignored for now).
            _ = await ws.receive_text()
    except Exception:
        manager.disconnect(ws)
