from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database.session import get_db
from backend.services.auth_service import get_current_user, require_admin
from backend.database.models import Camera, User
from backend.schemas.camera import CameraCreate, CameraUpdate, CameraResponse

from backend.services.camera_service import sync_active_cameras

router = APIRouter()

@router.post("/", response_model=CameraResponse, status_code=201)
def create_camera(
    camera: CameraCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Register a new camera stream (Admin only)."""
    db_camera = Camera(**camera.model_dump())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    
    # Trigger sync to start the stream if active
    sync_active_cameras()
    return db_camera

@router.get("/", response_model=List[CameraResponse])
def list_cameras(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all registered cameras."""
    cameras = db.query(Camera).offset(skip).limit(limit).all()
    return cameras

@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(
    camera_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific camera by ID."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera

@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int, 
    update_data: CameraUpdate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update camera details (Admin only)."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(camera, key, value)
    
    db.commit()
    db.refresh(camera)
    
    # Trigger sync to restart or stop the stream if changed
    sync_active_cameras()
    return camera

@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a camera (Admin only)."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    db.delete(camera)
    db.commit()
    
    # Trigger sync to stop the stream
    sync_active_cameras()
    return None

from fastapi.responses import StreamingResponse
from backend.services.camera_service import get_video_stream

@router.get("/{camera_id}/stream")
def stream_camera(camera_id: int):
    """Stream live MJPEG video from a camera."""
    return StreamingResponse(
        get_video_stream(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
