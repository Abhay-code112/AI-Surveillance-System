from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CameraBase(BaseModel):
    name: str = Field(..., description="Name of the camera (e.g. Front Door)")
    connection_url: str = Field(..., description="RTSP link, HTTP stream, or '0' for local webcam")
    location: Optional[str] = Field(None, description="Physical location")
    is_active: bool = Field(True, description="Whether the camera is currently monitored")

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    connection_url: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None

class CameraResponse(CameraBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
