"""
Products router — list and detail endpoints.

Endpoints:
    GET /api/v1/products           — paginated list of products
    GET /api/v1/products/{id}      — product detail with ingredient links
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.product import Product, ProductIngredient

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProductIngredientRead(BaseModel):
    id: int
    ingredient_id: int | None
    raw_name: str
    position: int
    match_method: str | None
    match_confidence: float | None
    extra_data: dict | None

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: int
    name: str
    brand: str | None
    category: str | None
    barcode: str | None
    product_risk_score: float | None
    extra_data: dict | None
    ingredients: list[ProductIngredientRead] = []

    model_config = {"from_attributes": True}


class ProductListItem(BaseModel):
    id: int
    name: str
    brand: str | None
    category: str | None
    barcode: str | None
    product_risk_score: float | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProductListItem])
def list_products(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return a paginated list of products (no ingredient detail)."""
    products = db.query(Product).offset(skip).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Return full product detail including all ingredient links."""
    product = (
        db.query(Product)
        .options(selectinload(Product.product_ingredients))
        .filter(Product.id == product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return ProductRead(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        barcode=product.barcode,
        product_risk_score=product.product_risk_score,
        extra_data=product.extra_data,
        ingredients=[
            ProductIngredientRead(
                id=pi.id,
                ingredient_id=pi.ingredient_id,
                raw_name=pi.raw_name,
                position=pi.position,
                match_method=pi.match_method,
                match_confidence=pi.match_confidence,
                extra_data=pi.extra_data,
            )
            for pi in product.product_ingredients
        ],
    )
