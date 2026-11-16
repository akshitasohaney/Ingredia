# backend/app/config.py
"""Application configuration for Ingredia backend.
Provides:
* `DATABASE_URL` – used by SQLAlchemy.
* `Settings` – pydantic‑style settings for runtime parameters.
* `get_settings()` – FastAPI‑compatible dependency returning a singleton.
"""

import os
from pathlib import Path
from typing import Final
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Repository root and database URL
# ---------------------------------------------------------------------------
ROOT_DIR: Final[Path] = Path(__file__).resolve().parents[2]
MATLAB_SCRIPTS_DIR: Final[Path] = Path(
    os.getenv("MATLAB_SCRIPTS_DIR", str(Path(__file__).resolve().parents[1] / "matlab"))
).resolve()
# Default to a local SQLite DB; can be overridden via the environment.
DATABASE_URL: Final[str] = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{ROOT_DIR / 'uploads' / 'ingredia.db'}",
)

# ---------------------------------------------------------------------------
# Runtime settings (used by the matching service)
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Configuration flags used by the matching service.
    All values are read from environment variables with sensible defaults.
    """
    fuzzy_auto_accept_threshold: float = 0.95
    fuzzy_suggest_threshold: float = 0.80

    model_config = ConfigDict(env_file=".env", case_sensitive=False)


# ---------------------------------------------------------------------------
# FastAPI dependency – returns a cached Settings instance.
# ---------------------------------------------------------------------------

_SETTINGS_SINGLETON: Settings | None = None

def get_settings() -> Settings:
    """Return a cached Settings instance.
    FastAPI can use this as a dependency (`Depends(get_settings)`), and the
    matching service imports it directly.
    """
    global _SETTINGS_SINGLETON
    if _SETTINGS_SINGLETON is None:
        _SETTINGS_SINGLETON = Settings()
    return _SETTINGS_SINGLETON
