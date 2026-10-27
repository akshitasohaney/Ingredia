"""
Products router – GET /api/v1/products
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.models.product import Product, ProductIngredient
from app.schemas.schemas import ProductRead, ProductDetail, RiskAnalysis, IngredientRisk

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List all products with pagination."""
    return db.query(Product).offset(skip).limit(limit).all()


@router.get("/search", response_model=list[ProductRead])
def search_products(query: str, db: Session = Depends(get_db)):
    """Search products by name or brand."""
    if not query or len(query.strip()) < 1:
        raise HTTPException(status_code=422, detail="Query must not be empty.")
    q = f"%{query.strip()}%"
    results = (
        db.query(Product)
        .filter(
            or_(
                Product.name.ilike(q),
                Product.brand.ilike(q),
            )
        )
        .limit(30)
        .all()
    )
    return results


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Return full product detail with ingredient list."""
    product = (
        db.query(Product)
        .options(
            joinedload(Product.product_ingredients).joinedload(ProductIngredient.ingredient)
        )
        .filter(Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.get("/{product_id}/risk", response_model=RiskAnalysis)
def get_risk_analysis(product_id: int, db: Session = Depends(get_db)):
    """
    Return an evidence-based risk analysis for a product.

    Important: ingredient presence alone does NOT determine safety.
    Concentration, formulation, exposure, and individual sensitivities all matter.
    These results are informational only.
    """
    product = (
        db.query(Product)
        .options(
            joinedload(Product.product_ingredients).joinedload(ProductIngredient.ingredient)
        )
        .filter(Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    ingredient_risks: list[IngredientRisk] = []
    unidentified = 0

    for pi in product.product_ingredients:
        ing = pi.ingredient
        if not ing:
            unidentified += 1
            continue

        # Simple heuristics for concern flags (never treat as definitive)
        is_concern = bool(ing.is_allergen or ing.caution_for)
        concern_reason: str | None = None
        if ing.is_allergen:
            concern_reason = "Potential allergen — may cause reactions in sensitised individuals."
        elif ing.caution_for:
            concern_reason = f"Caution advised for: {ing.caution_for}"

        ingredient_risks.append(
            IngredientRisk(
                ingredient_id=ing.id,
                name=ing.name,
                function=ing.function,
                description=ing.description,
                evidence_summary=ing.evidence_summary,
                evidence_source=ing.evidence_source,
                confidence_score=ing.confidence_score,
                suitable_for=ing.suitable_for,
                caution_for=ing.caution_for,
                is_fragrance=bool(ing.is_fragrance),
                is_allergen=bool(ing.is_allergen),
                is_concern=is_concern,
                concern_reason=concern_reason,
            )
        )

    return RiskAnalysis(
        product_id=product.id,
        product_name=product.name,
        brand=product.brand,
        product_type=product.product_type,
        intended_use=product.intended_use,
        ingredient_count=len(product.product_ingredients),
        unidentified_count=unidentified,
        ingredients=ingredient_risks,
    )
