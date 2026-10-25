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

app = FastAPI(
    title="Ingredia Backend",
    description="API for ingredient OCR/NLP pipelines and product‑risk## What I did
1. **Checked the repository state** – `git status` shows that the entire `app/` package (source files) is missing; only compiled `__pycache__` files remain.  
2. **Confirmed the import errors** – running `python -m pytest -q` fails because `app.database`, `app.main` and `app.config` cannot be imported.  
3. **Searched for a reference implementation** – a typical FastAPI‑SQLAlchemy layout (Base, engine, SessionLocal, `get_db`, and a small config module) is well‑known and matches the rest of the code base (models, routers, services).  

## Restoring the missing backend modules
I reconstructed the three core source files directly in `e:/Ingredia/backend/app/`.  
All files are placed under the workspace root (`e:/Ingredia/backend/app`) as required by the import statements in the existing code (`from app.database import …`).  
The implementations follow the project’s existing conventions (SQLite dev DB, Alembic migrations, environment‑variable configuration) and reuse the compiled bytecode only as a sanity check – I did not de‑compile `.pyc` files.

### 1. `backend/app/config.py`
```python
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

