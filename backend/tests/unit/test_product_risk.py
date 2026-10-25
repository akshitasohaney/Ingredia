# test_product_risk

"""Tests for the product risk assessment endpoint.

The tests use the in‑memory SQLite DB from `tests/conftest.py`. They create a
product with a couple of ingredients, some of which have hazard scores and
concerns, and verify that the `/products/{id}/risk` endpoint returns the
expected structure, version string and handles missing data correctly.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product, ProductIngredient
from app.models.ingredient import Ingredient, IngredientConcern


def create_product_with_ingredients(db: Session):
    # Create ingredients
    ing1 = Ingredient(
        canonical_name="Water",
        hazard_score=0.1,
        data_completeness="complete",
    )
    ing2 = Ingredient(
        canonical_name="Mystery",
        hazard_score=None,
        data_completeness="none",
    )
    db.add_all([ing1, ing2])
    db.flush()  # assign IDs

    # Add a concern for ing1
    concern = IngredientConcern(
        ingredient_id=ing1.id,
        concern_type="irritant",
        severity="suspected",
        summary="Mild skin irritant",
        source_name="ECHA",
    )
    db.add(concern)

    # Create product
    product = Product(name="Test Shampoo", brand="TestCo")
    db.add(product)
    db.flush()

    # Link ingredients to product
    pi1 = ProductIngredient(
        product_id=product.id,
        ingredient_id=ing1.id,
        raw_name="Water",
        position=1,
        match_method="exact",
        match_confidence=1.0,
    )
    pi2 = ProductIngredient(
        product_id=product.id,
        ingredient_id=ing2.id,
        raw_name="Mystery",
        position=2,
        match_method="unresolved",
        match_confidence=None,
    )
    db.add_all([pi1, pi2])
    db.commit()
    return product.id


def test_product_risk_endpoint(client: TestClient, db: Session):
    product_id = create_product_with_ingredients(db)
    resp = client.get(f"/api/v1/products/{product_id}/risk")
    assert resp.status_code == 200
    data = resp.json()
    # Basic fields
    assert data["product_id"] == product_id
    assert data["analysis_version"] == "v1.0"
    # Because one ingredient lacks a hazard score, overall risk is indeterminate
    assert data["product_risk_score"] is None
    # Verify ingredient findings list length
    assert len(data["ingredient_findings"]) == 2
    # Find Water entry
    water = next(i for i in data["ingredient_findings"] if i["raw_name"] == "Water")
    assert water["hazard_score"] == 0.1
    assert water["concerns"]  # at least one concern
    # Mystery entry missing hazard_score
    mystery = next(i for i in data["ingredient_findings"] if i["raw_name"] == "Mystery")
    assert mystery["hazard_score"] is None
    assert mystery["missing_data"] is True


def test_product_risk_invalid_id(client: TestClient):
    resp = client.get("/api/v1/products/99999/risk")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
