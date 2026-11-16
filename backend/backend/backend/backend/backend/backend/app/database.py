# backend/app/database.py
"""
SQLAlchemy engine, session factory, and declarative base for the Ingredia backend.

The rest of the codebase (models, routers, services) expects:
* `engine` – the DB engine.
* `SessionLocal` – a sessionmaker that produces DB sessions.
* `Base` – the declarative base used by ORM models.
* `get_db()` – FastAPI dependency that yields a session and closes it afterwards.
"""

from __future__ import annotations

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DATABASE_URL

# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": True}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

# --------------------------------------------------------------------------- #
# Session factory
# --------------------------------------------------------------------------- #
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --------------------------------------------------------------------------- #
# Declarative base – all ORM models inherit from this.
# --------------------------------------------------------------------------- #
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# --------------------------------------------------------------------------- #
# FastAPI dependency – yields a session and guarantees cleanup.
# --------------------------------------------------------------------------- #
def get_db():
    """Yield a DB session for a request and ensure it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Helper: create tables automatically for the dev environment.
# --------------------------------------------------------------------------- #
def init_db():
    """Create all tables. Used by the app on startup in dev mode."""
    from app import models  # noqa: F401 – import triggers model registration
    Base.metadata.create_all(bind=engine)


# Optional: log the DB connection on import (useful for debugging)
logging.getLogger(__name__).info("Database engine created – %s", DATABASE_URL)
