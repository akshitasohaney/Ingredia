"""
Ingredients router – GET /api/v1/ingredients
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.ingredient import Ingredient
from app.schemas.schemas import IngredientRead

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("/search", response_model=list[IngredientRead])
def search_ingredients(query: str, db: Session = Depends(get_db)):
    """Full-text search across ingredient name and aliases."""
    if not query or len(query.strip()) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters.")
    q = f"%{query.strip()}%"
    results = (
        db.query(Ingredient)
        .filter(
            or_(
                Ingredient.name.ilike(q),
                Ingredient.inci_name.ilike(q),
                Ingredient.aliases.ilike(q),
            )
        )
        .limit(30)
        .all()
    )
    return results


@router.get("/{ingredient_id}", response_model=IngredientRead)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    """Return a single ingredient by ID."""
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found.")
    return ing
