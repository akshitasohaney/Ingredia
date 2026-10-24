"""
Shared pytest fixtures for Ingredia backend tests.

Uses an in-memory SQLite DB to avoid touching the real ingredia.db.
The `client` fixture provides a FastAPI TestClient with the test DB injected
via dependency override.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# ── In-memory test database ───────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
def db():
    """
    Provide a clean, isolated DB session per test function.
    All tables are created fresh and dropped after the test completes.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    """
    FastAPI TestClient that uses the in-memory test DB.
    The real `get_db` dependency is overridden for the duration of the test.
    """
    def _override_get_db():
        try:
            yield db
        finally:
            pass  # Session lifecycle managed by the `db` fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
