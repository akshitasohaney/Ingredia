"""
Application configuration loaded from environment variables or a .env file.
All fields have development-safe defaults so the app runs with zero config.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels up from this file: backend/app/config.py → backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'ingredia.db'}"

    # ── File storage ───────────────────────────────────────────────────────────
    uploads_dir: Path = BACKEND_ROOT / "uploads"

    # ── NLP matching thresholds ────────────────────────────────────────────────
    # Tokens with fuzzy score ≥ auto_accept_threshold are accepted without review
    fuzzy_auto_accept_threshold: float = 0.95
    # Tokens with score ≥ suggest_threshold are surfaced as suggestions
    fuzzy_suggest_threshold: float = 0.85

    # ── OCR ────────────────────────────────────────────────────────────────────
    # Words with Tesseract confidence below this are highlighted in the review UI
    ocr_word_confidence_flag: float = 60.0
    # Minimum image width (px) before upscaling
    ocr_min_image_width: int = 1500

    # ── App metadata ───────────────────────────────────────────────────────────
    app_name: str = "Ingredia"
    app_version: str = "0.1.0"
    debug: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (safe for FastAPI Depends)."""
    return Settings()
