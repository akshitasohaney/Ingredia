"""
Ingredia FastAPI application factory.

Routers are registered here; their implementations live in app/routers/.
The lifespan context manager handles startup tasks (e.g. ensuring upload dir exists).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup; yields; runs once at shutdown."""
    settings = get_settings()
    # Ensure the uploads directory exists
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    yield
    # (shutdown logic goes here if needed)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Ingredia API — understand the safety of ingredients "
            "in cosmetics and personal-care products."
        ),
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    # In development, allow the Vite dev server origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    # Imported here to avoid circular imports at module level
    from app.routers import ingredients, products, scans

    app.include_router(ingredients.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")
    app.include_router(scans.router, prefix="/api/v1")

    # ── Health check ───────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
