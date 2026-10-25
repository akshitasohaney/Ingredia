#!/usr/bin/env python
"""
Run the real-data import against a fresh in-memory SQLite database
and print a structured report.

Usage:
    python scripts/run_real_import_check.py

This script NEVER touches the development database (ingredia.db).
"""

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app.database import Base  # noqa: E402
from scripts.import_api_data import run_import  # noqa: E402

# ── Temporary in-memory database ──────────────────────────────────────────────
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=engine)
TempSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ── First import ──────────────────────────────────────────────────────────────
print("=" * 70)
print("PASS 1 — First import (expect insertions)")
print("=" * 70)
session1 = TempSession()
uploads_dir = backend_root / "uploads"
try:
    result1 = run_import(uploads_dir=uploads_dir, db=session1)
    session1.commit()
finally:
    session1.close()

print(json.dumps(result1, indent=2))

# Summarise first pass
for frep in result1["files"]:
    n_rejected = len(frep["rejected"])
    print(
        f"\n[{frep['file']}] "
        f"src={frep['source_rows']} ins={frep['inserted']} "
        f"upd={frep['updated']} unch={frep['unchanged']} "
        f"skip={frep['skipped']} rej={n_rejected}"
    )
    if frep["rejected"]:
        print(f"  First 5 rejections:")
        for r in frep["rejected"][:5]:
            print(f"    row {r['row']}: {r['reason']}")

# ── Second import (idempotency check) ─────────────────────────────────────────
print("\n" + "=" * 70)
print("PASS 2 — Second import (expect ZERO insertions/updates)")
print("=" * 70)
session2 = TempSession()
try:
    result2 = run_import(uploads_dir=uploads_dir, db=session2)
    session2.commit()
finally:
    session2.close()

for frep in result2["files"]:
    n_rejected = len(frep["rejected"])
    print(
        f"[{frep['file']}] "
        f"ins={frep['inserted']} upd={frep['updated']} "
        f"unch={frep['unchanged']} rej={n_rejected}"
    )

idempotent = result2["total_inserted"] == 0 and result2["total_updated"] == 0
status_str = "PASS" if idempotent else "FAIL"
print(
    f"\nIdempotency: {status_str} "
    f"(inserted={result2['total_inserted']}, updated={result2['total_updated']})"
)


# ── Quick DB row counts ────────────────────────────────────────────────────────
from app.models.ingredient import Ingredient, IngredientAlias  # noqa: E402
from app.models.product import Product, ProductIngredient  # noqa: E402

session3 = TempSession()
try:
    print("\n" + "=" * 70)
    print("DATABASE ROW COUNTS AFTER IMPORT")
    print("=" * 70)
    print(f"  ingredients:        {session3.query(Ingredient).count()}")
    print(f"  ingredient_aliases: {session3.query(IngredientAlias).count()}")
    print(f"  products:           {session3.query(Product).count()}")
    print(f"  product_ingredients:{session3.query(ProductIngredient).count()}")
finally:
    session3.close()
