"""Ingredient API routes (Milestone 2)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientRead,
    IngredientDetail,
    IngredientUpdate,
    PaginatedIngredients,
    IngredientConcernCreate,
    IngredientConcernRead,
)
from app.services.ingredient_service import (
    list_ingredients,
    get_ingredient_by_id,
    create_ingredient,
    update_ingredient,
    delete_ingredient,
    list_concerns,
    add_concern,
)

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

# ---------- Collection endpoints ----------
@router.get("/", response_model=PaginatedIngredients)
def get_ingredients(
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    concern_type: str | None = None,
    min_hazard: float | None = None,
    max_hazard: float | None = None,
    data_completeness: str | None = None,
    eu_annex_status: str | None = None,
    db: Session = Depends(get_db),
):
    total, items = list_ingredients(
        db,
        skip=skip,
        limit=limit,
        search=search,
        concern_type=concern_type,
        min_hazard=min_hazard,
        max_hazard=max_hazard,
        data_completeness=data_completeness,
        eu_annex_status=eu_annex_status,
    )
    return PaginatedIngredients(total=total, skip=skip, limit=limit, items=items)

@router.post(
    "/",
    response_model=IngredientDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_new_ingredient(payload: IngredientCreate, db: Session = Depends(get_db)):
    try:
        ingredient = create_ingredient(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    ingredient = get_ingredient_by_id(db, ingredient.id)
    return IngredientDetail.from_orm(ingredient)

# ---------- Single‑item endpoints ----------
@router.get("/{ingredient_id}", response_model=IngredientDetail)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    ingredient = get_ingredient_by_id(db, ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return IngredientDetail.from_orm(ingredient)

@router.patch("/{ingredient_id}", response_model=IngredientDetail)
def patch_ingredient(ingredient_id: int, payload: IngredientUpdate, db: Session = Depends(get_db)):
    ingredient = update_ingredient(db, ingredient_id, payload)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient = get_ingredient_by_id(db, ingredient.id)
    return IngredientDetail.from_orm(ingredient)

@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient_endpoint(ingredient_id: int, db: Session = Depends(get_db)):
    deleted = delete_ingredient(db, ingredient_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return None

# ---------- Concern sub‑resource ----------
@router.get("/{ingredient_id}/concerns", response_model=list[IngredientConcernRead])
def get_concerns(ingredient_id: int, db: Session = Depends(get_db)):
    if not get_ingredient_by_id(db, ingredient_id):
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return list_concerns(db, ingredient_id)

@router.post(
    "/{ingredient_id}/concerns",
    response_model=IngredientConcernRead,
    status_code=status.HTTP_201_CREATED,
)
def create_concern(ingredient_id: int, payload: IngredientConcernCreate, db: Session = Depends(get_db)):
    concern = add_concern(db, ingredient_id, payload)
    if concern is None:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return concern

