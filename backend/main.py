"""FastAPI application entry point for the AI CCTV Surveillance API.

Run with:
    uvicorn backend.main:app --reload

Then open http://127.0.0.1:8000/docs for the interactive Swagger UI.

Architecture
------------
This file is intentionally thin.  It only does three things:

1. **Configure logging** so every module uses Python's standard logger.
2. **Register routers** — each route file handles its own endpoints.
3. **Run startup tasks** — create database tables and storage directories.

All business logic lives in ``services/``, all data shapes in ``schemas/``,
and all database code in ``database/``.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.database.session import init_db
from backend.routes import health, predictions, events, jobs, alerts, cameras, analytics, auth
from backend.routes.ws import router as ws_router

import uuid
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_ctx_var = contextvars.ContextVar("request_id", default="-")

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx_var.get()
        return True

# ── Logging setup ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ [%(request_id)s] │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Apply filter to root logger so all logs get request_id
for handler in logging.root.handlers:
    handler.addFilter(RequestIDFilter())

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        token = request_id_ctx_var.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx_var.reset(token)


# ── Application lifespan ──────────────────────────────────────────
# Code inside this block runs ONCE when the server starts, and the
# ``yield`` marks where the app is "running".  Anything after ``yield``
# would run on shutdown (we don't need shutdown logic yet).
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the FastAPI application."""
    logger.info("=" * 60)
    logger.info("  %s  v%s", settings.PROJECT_NAME, settings.VERSION)
    logger.info("=" * 60)

    # Create database tables (if they don't exist yet)
    init_db()
    logger.info("Database initialised.")

    # Ensure storage directories exist
    project_root = Path(__file__).resolve().parent.parent
    for subdir in ("storage/uploads", "storage/clips", "storage/screenshots"):
        (project_root / subdir).mkdir(parents=True, exist_ok=True)
    logger.info("Storage directories verified.")

    # Start background streams for active cameras
    from backend.services.camera_service import sync_active_cameras
    sync_active_cameras()
    logger.info("Camera streams synchronized.")

    from backend.services.retention_service import start_retention_service
    start_retention_service()

    logger.info("Server is ready.  Visit http://127.0.0.1:8000/docs")
    logger.info("-" * 60)

    yield  # ← Server is running. Requests are handled here.

    # Graceful shutdown: stop all camera threads
    from backend.services.camera_service import stop_camera, _camera_threads
    for cam_id in list(_camera_threads.keys()):
        stop_camera(cam_id)
    logger.info("Camera streams stopped.")
    
    from backend.services.retention_service import stop_retention_service
    stop_retention_service()
    
    # Close DB engine
    from backend.database.session import engine
    engine.dispose()
    logger.info("Database connection closed.")
    
    # Flush logs
    for handler in logging.root.handlers:
        handler.flush()
        
    logger.info("Shutting down …")


# ── FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Backend API for the AI CCTV Surveillance Platform.\n\n"
        "**Capabilities:**\n"
        "- Upload videos for violence and activity detection\n"
        "- Real-time camera stream monitoring\n"
        "- Query surveillance event history\n"
        "- Analytics and reporting dashboard\n"
        "- JWT authentication and role-based access\n"
        "- System health monitoring\n\n"
        "Built with FastAPI + PyTorch + SQLAlchemy."
    ),
    lifespan=lifespan,
)

# ── CORS middleware ───────────────────────────────────────────────
# This allows the React/Streamlit frontend (running on a different port)
# to make requests to our API without being blocked by the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

# ── Global Exception Handlers ─────────────────────────────────────
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception:")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."}
    )


# ── Register routers ─────────────────────────────────────────────
app.include_router(health.router,      prefix="/api", tags=["System"])
app.include_router(predictions.router, prefix="/api", tags=["Predictions (Sync)"])
app.include_router(jobs.router,        prefix="/api", tags=["Jobs (Async)"])
app.include_router(events.router,      prefix="/api", tags=["Events"])
app.include_router(alerts.router,      prefix="/api", tags=["Alerts"])
app.include_router(cameras.router,     prefix="/api/cameras", tags=["Cameras"])
app.include_router(analytics.router,   prefix="/api/analytics", tags=["Analytics"])
app.include_router(auth.router,        prefix="/api/auth", tags=["Authentication"])
app.include_router(ws_router,          prefix="/ws", tags=["WebSocket"])


@app.get("/", tags=["System"])
def root():
    """Root endpoint — confirms the API is reachable."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }
