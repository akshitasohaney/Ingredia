"""
Test fixtures for the Ingredia backend.
Provides a FastAPI TestClient with a temporary SQLite database for each test.
"""

import sys, os
import pytest
from fastapi.testclient import TestClient
# Ensure the backend package is on the import path for tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app
from app.database import Base, engine, SessionLocal, get_db

# ---------- Database fixture ----------
@pytest.fixture(scope="function")
def db():
    """Create a fresh database for a test and drop it afterwards."""
    # Ensure tables are created
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables to clean up
        Base.metadata.drop_all(bind=engine)

# ---------- Client fixture ----------
@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient that uses the test database session."""
    # Override the FastAPI dependency to use the test DB session
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    # Clean up overrides after the test
    app.dependency_overrides.clear()
