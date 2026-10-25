# backend/app/main.py
"""
FastAPI entry point for the Ingredia backend.

* Includes the API routers (`/api/v1/scans`, `/api/v1/products`, …).
* Calls `init_db()` on startup so the SQLite dev DB is ready.
* Exposes the `app` object that `uvicorn` or the test client uses.
"""

from fastapi import FastAPI
from .database import init_db

# Import routers – they register their endpoints when the module is imported.
from app.routers import scans, products, health  # type: ignore

def on_startup() -> None:
    """Create tables if they do not exist (dev convenience)."""
    init_db()

app = FastAPI(
    title="Ingredia Backend",
    description="API for ingredient OCR/NLP pipelines and product‑risk analysis.",
    version="0.1.0",
    on_startup=[on_startup],
)

app.include_router(scans.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
