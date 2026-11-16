#!/usr/bin/env python
"""Integration tests for the CSV import script.

The tests create a temporary uploads directory with minimal CSV files
matching the expected schema, invoke :func:`run_import` with the in‑memory
test database fixture, and assert that the summary reflects successful
inserts and no errors.
"""

import csv
from pathlib import Path
import pytest

from app.config import get_settings
from app.database import Base
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.product import Product, ProductIngredient
from app.scripts.import_api_data import run_import

# Helper to write a CSV file with a header and rows
def _write_csv(path: Path, header: list[str], rows: list[tuple]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

@pytest.fixture(scope="function")
def uploads_dir(tmp_path: Path):
    """Create a temporary uploads directory containing the four CSV files."""
    # Ingredients
    _write_csv(
        tmp_path / "api_ingredients.csv",
        [
            "canonical_name",
            "cas_number",
            "ec_number",
            "function_tags",
            "hazard_score",
            "hazard_basis",
            "data_completeness",
            "ewg_score",
            "eu_annex_status",
            "eu_annex_a",
        ],
        [
            (
                "Water",
                "7732-18-5",
                "231-791-2",
                "[\"solvent\"]",
                "0",
                "in_vitro",
                "complete",
                "1",
                "permitted",
                "yes",
            ),
        ],
    )
    # Aliases
    _write_csv(
        tmp_path / "api_ingredient_aliases.csv",
        ["canonical_name", "alias", "alias_type"],
        [("Water", "Aqua", "common")],
    )
    # Products
    _write_csv(
        tmp_path / "api_products.csv",
        ["product_id", "name", "brand", "category", "barcode", "product_risk_score", "risk_computed_at"],
        [("1", "Sample Shampoo", "BrandX", "Hair", "1234567890123", "2.5", "2023-01-01")],
    )
    # Product‑Ingredient links
    _write_csv(
        tmp_path / "api_product_ingredients.csv",
        [
            "product_id",
            "ingredient_id",
            "raw_name",
            "position",
            "match_method",
            "match_confidence",
        ],
        [("1", "1", "Water", "1", "exact", "1.0")],
    )
    return tmp_path

def test_import_success(db, uploads_dir: Path):
    """Run the import script and validate the summary and DB state."""
    summary = run_import(uploads_dir=uploads_dir, db=db)
    # Expect all rows to be inserted without errors
    assert summary["missing_files"] == []
    assert summary["failed"] == 0
    assert summary["rejected"] == 0
    # At least one of each entity type should be inserted
    assert summary["inserted"] >= 4
    # Verify that the ingredient was persisted correctly
    water = db.query(Ingredient).filter_by(canonical_name="Water").one_or_none()
    assert water is not None
    assert water.cas_number == "7732-18-5"
    # extra_data should contain the eu_annex flag
    assert water.extra_data.get("eu_annex_flags") == ["yes"]
    # Alias should be linked to the ingredient
    alias = db.query(IngredientAlias).filter_by(alias="Aqua").one_or_none()
    assert alias is not None
    assert alias.ingredient_id == water.id
    # Product and link
    product = db.query(Product).filter_by(name="Sample Shampoo").one_or_none()
    assert product is not None
    link = (
        db.query(ProductIngredient)
        .filter_by(product_id=product.id, ingredient_id=water.id)
        .one_or_none()
    )
    assert link is not None
    assert link.raw_name == "Water"
