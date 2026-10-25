# backend/app/config.py
"""
Application configuration for Ingredia backend.

* Reads environment variables (fallback to sane defaults).
* Provides the DATABASE_URL used by SQLAlchemy.
* Keeps configuration minimal – the rest of the code expects only `DATABASE_URL`.
"""

import os
from pathlib import Path
from typing import Final

# Root of the repository (two levels up from this file)
ROOT_DIR: Final[Path] = Path(__file__).resolve().parents[2]

# Default to a local SQLite database (the development DB lives in `uploads/ingredia.db`).
# Users can override via the DATABASE_URL environment variable.
DATABASE_URL: Final[str] = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{ROOT_DIR / 'uploads' / 'ingredia.db'}"
)
