# backend/app/routers/health.py
"""Health check router for the Ingredia backend.
Provides a simple `/health` endpoint returning `{\"status\": \"ok\"}`.
This satisfies the `app.main` import and is used by integration tests.
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    """Return a basic health‑check payload.

    The test suite expects the router to be importable as `health` and
    mounted under the `/api/v1` prefix.
    """
    return {"status": "ok"}
