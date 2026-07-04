"""Database engine and session management.

Uses SQLite for development. Can be swapped to PostgreSQL
by changing DATABASE_URL in .env.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from backend.config.settings import settings

logger = logging.getLogger(__name__)

from sqlalchemy import event

import os

# Create engine — check_same_thread is needed for SQLite only
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    
    # Ensure the directory exists
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path != ":memory:":
        db_dir = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.
    
    Yields a session and ensures it is closed after the request,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables.
    
    Called once on application startup.
    """
    from backend.database.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")
