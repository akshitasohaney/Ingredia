"""
Business logic for the Ingredient domain.

All DB interactions are here; routers call these functions and deal only
with HTTP concerns (status codes, response models).

Design decisions:
- function_tags is serialised to JSON string before writing to DB and
  deserialised by the Pydantic schema on the way out.
- PATCH updates only the fields explicitly set in the request (exclude_unset).
- Hazard score invalidation: updating an ingredient does NOT automatically
  invalidate product_risk_scores — that happens in product_service when
  product_ingredients change.
"""

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.ingredient import Ingredient, IngredientAlias, IngredientConcern
from app.schemas.ingredient import (
    IngredientConcernCreate,
    IngredientCreate,
    IngredientUpdate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialise_function_tags(tags: list[str] | None) -> str | None:
    """Convert list → JSON string for DB storage."""
    if tags is None:
        return None
    return json.dumps(tags)


# ── Read operations ───────────────────────────────────────────────────────────


def get_ingredient_by_id(db: Session, ingredient_id: int) -> Ingredient | None:
    """Return a single ingredient with concerns and aliases eager-loaded."""
    return (
        db.execute(
            select(Ingredient)
            .where(Ingredient.id == ingredient_id)
            .options(
                selectinload(Ingredient.concerns),
                selectinload(Ingredient.aliases),
            )
        )
        .scalars()
        .first()
    )


def get_ingredient_by_name(db: Session, canonical_name: str) -> Ingredient | None:
    return (
        db.execute(
            select(Ingredient).where(Ingredient.canonical_name == canonical_name)
        )
        .scalars()
        .first()
    )


def list_ingredients(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    concern_type: str | None = None,
    min_hazard: float | None = None,
    max_hazard: float | None = None,
    data_completeness: str | None = None,
    eu_annex_status: str | None = None,
) -> tuple[int, list[Ingredient]]:
    """
    Return (total_count, page_of_ingredients).

    Filters:
      - search: case-insensitive substring match on canonical_name
      - concern_type: only ingredients that have at least one concern of this type
      - min_hazard / max_hazard: hazard_score range (NULL scores are excluded from range filters)
      - data_completeness: exact match
      - eu_annex_status: exact match
    """
    query = select(Ingredient)

    if search:
        query = query.where(
            Ingredient.canonical_name.ilike(f"%{search}%")
        )

    if concern_type:
        # Semi-join: ingredient must have at least one concern of this type
        query = query.where(
            Ingredient.id.in_(
                select(IngredientConcern.ingredient_id).where(
                    IngredientConcern.concern_type == concern_type
                )
            )
        )

    if min_hazard is not None:
        query = query.where(
            Ingredient.hazard_score.is_not(None),
            Ingredient.hazard_score >= min_hazard,
        )

    if max_hazard is not None:
        query = query.where(
            Ingredient.hazard_score.is_not(None),
            Ingredient.hazard_score <= max_hazard,
        )

    if data_completeness:
        query = query.where(Ingredient.data_completeness == data_completeness)

    if eu_annex_status:
        query = query.where(Ingredient.eu_annex_status == eu_annex_status)

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total: int = db.execute(count_query).scalar_one()

    # Apply ordering and pagination
    query = query.order_by(Ingredient.canonical_name).offset(skip).limit(limit)
    items = db.execute(query).scalars().all()

    return total, list(items)


def list_concerns(db: Session, ingredient_id: int) -> list[IngredientConcern]:
    return (
        db.execute(
            select(IngredientConcern).where(
                IngredientConcern.ingredient_id == ingredient_id
            )
        )
        .scalars()
        .all()
    )


# ── Write operations ──────────────────────────────────────────────────────────


def create_ingredient(db: Session, data: IngredientCreate) -> Ingredient:
    """
    Create a new ingredient.
    Raises ValueError if canonical_name already exists.
    """
    existing = get_ingredient_by_name(db, data.canonical_name)
    if existing:
        raise ValueError(
            f"Ingredient with canonical_name '{data.canonical_name}' already exists."
        )

    ingredient = Ingredient(
        canonical_name=data.canonical_name,
        cas_number=data.cas_number,
        ec_number=data.ec_number,
        function_tags=_serialise_function_tags(data.function_tags),
        hazard_score=data.hazard_score,
        hazard_basis=data.hazard_basis,
        data_completeness=data.data_completeness,
        ewg_score=data.ewg_score,
        eu_annex_status=data.eu_annex_status,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def update_ingredient(
    db: Session, ingredient_id: int, data: IngredientUpdate
) -> Ingredient | None:
    """
    Partial update — only fields explicitly set in the request are written.
    Returns None if ingredient not found.
    """
    ingredient = get_ingredient_by_id(db, ingredient_id)
    if ingredient is None:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # function_tags needs serialisation if present
    if "function_tags" in update_data:
        update_data["function_tags"] = _serialise_function_tags(
            update_data["function_tags"]
        )

    for field, value in update_data.items():
        setattr(ingredient, field, value)

    db.commit()
    db.refresh(ingredient)
    return ingredient


def add_concern(
    db: Session, ingredient_id: int, data: IngredientConcernCreate
) -> IngredientConcern | None:
    """
    Add a concern to an ingredient.
    Returns None if the ingredient does not exist.
    source_name is required by the schema — this is enforced at the Pydantic layer.
    """
    ingredient = get_ingredient_by_id(db, ingredient_id)
    if ingredient is None:
        return None

    concern = IngredientConcern(
        ingredient_id=ingredient_id,
        concern_type=data.concern_type,
        severity=data.severity,
        summary=data.summary,
        source_name=data.source_name,
        source_url=data.source_url,
        population_context=data.population_context,
    )
    db.add(concern)
    db.commit()
    db.refresh(concern)
    return concern


def delete_ingredient(db: Session, ingredient_id: int) -> bool:
    """
    Hard delete an ingredient and all its aliases/concerns (CASCADE).
    Returns True if deleted, False if not found.
    """
    ingredient = get_ingredient_by_id(db, ingredient_id)
    if ingredient is None:
        return False
    db.delete(ingredient)
    db.commit()
    return True
