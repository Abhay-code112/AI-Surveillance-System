from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import torch

from backend.database.session import get_db

router = APIRouter()

import os
from pathlib import Path
from backend.config.settings import settings
from backend.services.camera_service import _camera_threads

class HealthResponse(BaseModel):
    status: str
    database: str
    gpu_available: bool
    device_name: str
    camera_service: str
    storage: str
    version: str

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Check if the API is running, verify database, and check GPU.
    """
    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

    # 2. GPU check
    gpu_ok = torch.cuda.is_available()
    device = torch.cuda.get_device_name(0) if gpu_ok else "CPU"
    
    # 3. Camera Service
    active_threads = len([t for t in _camera_threads.values() if t.is_alive()])
    camera_status = f"{active_threads} active streams"
    
    # 4. Storage check
    project_root = Path(__file__).resolve().parent.parent.parent
    upload_dir = project_root / "storage/uploads"
    storage_ok = os.access(upload_dir, os.W_OK)
    storage_status = "writable" if storage_ok else "read-only"
    
    return HealthResponse(
        status="healthy",
        database=db_status,
        gpu_available=gpu_ok,
        device_name=device,
        camera_service=camera_status,
        storage=storage_status,
        version=settings.VERSION,
    )
