"""Authentication schemas — request/response models for auth endpoints (Phase 11).

Learning notes
--------------
* ``SecretStr`` in Pydantic hides the password from logs and repr.
* We separate ``UserCreate`` (registration input), ``UserLogin`` (login input),
  and ``UserResponse`` (what we return — never includes the password hash).
* The ``TokenResponse`` is what the frontend stores in localStorage.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    """Registration request body."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field("viewer", description="'admin' or 'viewer'")


class UserLogin(BaseModel):
    """Login request body."""
    username: str
    password: str


class UserResponse(BaseModel):
    """User data returned in API responses (no password!)."""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token returned after successful login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    user: UserResponse
