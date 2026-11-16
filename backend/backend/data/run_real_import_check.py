#!/usr/bin/env python
"""Run the real CSV import against a temporary in‑memory SQLite database and verify.

The script:
1. Checks that the four required CSV files exist in `backend/uploads/`.
2. Prints each file's header fields and row count.
3. Creates an in‑memory SQLite engine, a Session, and calls `run_import`.
4. Prints the import summary.
5. Re‑runs the import to confirm idempotency (no extra inserts/updates).
6. Performs a few sanity checks on the persisted data (function_tags parsing,
   EU annex flags in `extra_data`, foreign‑key relationships).
7. Starts a FastAPI TestClient with the same temporary DB and fetches a sample
   ingredient and product to demonstrate the API works with the imported data.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Adjust sys.path so project modules can be imported when this script is run
repo_root = Path('e:/Ingredia')
backend_path = repo_root / 'backend'
sys.path.insert(0, str(backend_path))

from app.config import get_settings
from app.database import Base, get_db
from app.scripts.import_api_data import run_import
from app.main import app

UPLOADS_DIR = Path(repo_root) / "backend" / "uploads"
required_files = {
    "ingredients": UPLOADS_DIR / "api_ingredients.csv",
    "aliases": UPLOADS_DIR / "api_ingredient_aliases.csv",
    "products": UPLOADS_DIR / "api_products.csv",
    "product_ingredients": UPLOADS_DIR / "api_product_ingredients.csv",
}

# 1. Verify existence
missing = [name for name, p in required_files.items() if not p.is_file()]
if missing:
    print("Missing required CSV files:")
    for name in missing:
        print(f"  {name}: {required_files[name]}")
    sys.exit(1)

print("All required CSV files are present.\n")

# 2. Inspect headers and row counts
for name, path in required_files.items():
    with path.open(newline="", encoding="utf-8") as f:
        header = f.readline().strip()
        rows = sum(1 for _ in f)
    print(f"{name}: header={header.split(',')}")
    print(f"{name}: rows={rows}\n")

# 3. Create temporary in‑memory DB
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)
session = SessionLocal()

# 4. First import
summary1 = run_import(uploads_dir=UPLOADS_DIR, db=session)
print("First import summary:")
print(json.dumps(summary1, indent=2))

# 5. Second import (idempotency)
summary2 = run_import(uploads_dir=UPLOADS_DIR, db=session)
print("\nSecond import summary (should show no new inserts/updates):")
print(json.dumps(summary2, indent=2))

# 6. Basic data sanity checks
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.product import Product, ProductIngredient

print("\nDatabase record counts after import:")
print(f"Ingredients: {session.query(Ingredient).count()}")
print(f"Aliases: {session.query(IngredientAlias).count()}")
print(f"Products: {session.query(Product).count()}")
print(f"ProductIngredient links: {session.query(ProductIngredient).count()}")

# Sample ingredient
first_ing = session.query(Ingredient).first()
if first_ing:
    print("\nSample ingredient record:")
    print(f"canonical_name={first_ing.canonical_name}")
    print(f"function_tags={first_ing.function_tags}")
    print(f"extra_data={first_ing.extra_data}")
    if first_ing.extra_data and "eu_annex_flags" in first_ing.extra_data:
        print("EU annex flags preserved:", first_ing.extra_data["eu_annex_flags"])
else:
    print("No ingredients imported.")

# 7. FastAPI TestClient using same DB session
def _override_get_db():
    try:
        yield session
    finally:
        pass

app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

if first_ing:
    resp = client.get(f"/api/v1/ingredients/{first_ing.id}")
    print("\nAPI response for sample ingredient (status code, keys):")
    print(resp.status_code)
    print(resp.json().keys())

first_product = session.query(Product).first()
if first_product:
    prod_resp = client.get(f"/api/v1/products/{first_product.id}")
    print("\nAPI response for sample product (status code, keys):")
    print(prod_resp.status_code)
    print(prod_resp.json().keys())
else:
    print("No products imported.")

# Clean up
app.dependency_overrides.clear()
session.close()
engine.dispose()
print("\nScript completed.")
