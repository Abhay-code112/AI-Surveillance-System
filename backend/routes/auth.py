"""Authentication routes — register, login, and user management (Phase 11).

Endpoints
---------
* ``POST /api/auth/register``  — create a new user account.
* ``POST /api/auth/login``     — authenticate and receive a JWT token.
* ``GET  /api/auth/me``        — return the current user's profile (protected).

Learning notes
--------------
* Registration hashes the password with bcrypt before storing.
* Login verifies the hash, then creates a JWT token.
* The ``/me`` endpoint uses ``Depends(get_current_user)`` — this is
  FastAPI's dependency injection system.  It automatically reads the
  ``Authorization: Bearer <token>`` header, decodes the JWT, looks up
  the user in the DB, and passes the ``User`` object to your function.
  If anything fails, it returns a 401 automatically.
* This pattern means you can protect ANY endpoint just by adding
  ``user: User = Depends(get_current_user)`` to its parameters.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.database.models import User
from backend.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from backend.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
    rate_limit,
)
from backend.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(rate_limit)])
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account.

    **Request body:**
    ```json
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "secretpass",
        "role": "admin"
    }
    ```

    **Rules:**
    * Username and email must be unique.
    * Password must be at least 6 characters.
    * Role must be ``admin`` or ``viewer`` (default: ``viewer``).
    """
    # Check for existing username
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken.",
        )

    # Check for existing email
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{payload.email}' is already registered.",
        )

    # Validate role
    if payload.role not in ("admin", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be 'admin' or 'viewer'.",
        )

    from backend.services.auth_service import validate_password
    try:
        validate_password(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("User '%s' registered (role=%s).", user.username, user.role)
    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit)])
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and return a JWT token.

    **Request body:**
    ```json
    {
        "username": "admin",
        "password": "secretpass"
    }
    ```

    **Response:**
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "token_type": "bearer",
        "expires_in": 28800,
        "user": { "id": 1, "username": "admin", ... }
    }
    ```
    """
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    token = create_access_token(user.username, user.role)
    logger.info("User '%s' logged in.", user.username)

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile.

    Requires a valid JWT token in the ``Authorization: Bearer`` header.
    """
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(user: User = Depends(get_current_user)):
    """Refresh the current JWT token silently.
    
    Allows the frontend to stay logged in continuously without forcing
    the user to enter their password again, as long as their token hasn't
    fully expired yet.
    """
    token = create_access_token(user.username, user.role)
    logger.info("User '%s' refreshed token.", user.username)

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )
