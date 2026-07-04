"""Authentication service — password hashing & JWT tokens (Phase 11).

This module handles the two core security operations:

1. **Password hashing** with bcrypt (via ``passlib``).
2. **JWT token creation/verification** (via ``python-jose``).

Learning notes
--------------
* **bcrypt** is a one-way hash — you can never "decrypt" the password.
  To verify a login, you hash the submitted password and compare the
  hashes.  ``passlib`` handles the salting automatically.
* **JWT (JSON Web Token)** is a signed JSON payload.  The server creates
  it at login, the frontend stores it (usually in localStorage), and
  sends it as ``Authorization: Bearer <token>`` on every request.
* ``python-jose`` is a popular JWT library for Python.  The ``HS256``
  algorithm uses a shared secret (``JWT_SECRET_KEY``).
* We embed the ``sub`` (subject = username) and ``exp`` (expiration)
  claims in the token payload.  FastAPI's ``Depends`` system lets us
  extract the current user from the token automatically.

Security checklist
------------------
* Never store plain-text passwords.
* Never log passwords or tokens.
* Set ``JWT_SECRET_KEY`` to a long random string in ``.env``.
* Set ``JWT_EXPIRE_MINUTES`` to a reasonable value (8 hours default).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.config.settings import settings
from backend.database.session import get_db
from backend.database.models import User

logger = logging.getLogger(__name__)

# ── Password hashing ─────────────────────────────────────────────
# We use the standard ``bcrypt`` library directly.

def hash_password(plain: str) -> str:
    """Hash a plain-text password for database storage."""
    # bcrypt requires bytes
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(plain.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against a stored hash."""
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


# ── JWT token operations ─────────────────────────────────────────
# The token payload looks like: {"sub": "username", "exp": 1720000000}

def create_access_token(username: str, role: str) -> str:
    """Create a signed JWT access token.

    Parameters
    ----------
    username : str
        The user's unique username (becomes the ``sub`` claim).
    role : str
        The user's role (``admin`` or ``viewer``).

    Returns
    -------
    str
        The encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Raises ``JWTError`` if the token is invalid or expired.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── FastAPI dependency for protected routes ───────────────────────
# ``OAuth2PasswordBearer`` tells Swagger UI to show a "lock" icon and
# send the token as ``Authorization: Bearer <token>``.

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — extracts and validates the current user from the JWT.

    Usage in a route::

        @router.get("/protected")
        def protected_endpoint(user: User = Depends(get_current_user)):
            return {"message": f"Hello {user.username}!"}

    Raises
    ------
    HTTPException (401)
        If the token is missing, invalid, expired, or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: Ensures the current user has the 'admin' role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user

import time
from collections import defaultdict
from fastapi import Request

_rate_limits = defaultdict(list)
RATE_LIMIT_MAX = 5 # requests
RATE_LIMIT_WINDOW = 60 # seconds

def rate_limit(request: Request):
    """Dependency: Rate limit based on client IP."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    history = _rate_limits[ip]
    _rate_limits[ip] = [t for t in history if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limits[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    _rate_limits[ip].append(now)


import re

def validate_password(password: str):
    """Enforce strict password requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character.")
