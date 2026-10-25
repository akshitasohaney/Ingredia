

"""Risk analysis service for Ingredia.

This module provides a transparent, versioned implementation for computing a
product's risk score based on its associated ingredients, their hazard scores,
and any documented concerns. The logic deliberately avoids making scientific
assumptions about safety; it only aggregates the evidence that is present in the
database.

Key design goals:
- **Explainability** – the result contains per‑ingredient findings, the raw
  hazard score, a list of concerns (with source information), and flags for any
  missing data.
- **Versioning** – the ``ANALYSIS_VERSION`` constant allows downstream services
  to detect which algorithm produced the result.
- **Safety** – if any ingredient lacks a hazard score we treat the overall risk
  as indeterminate (``None``) rather than guessing a value.
- **No invented data** – we never fabricate concentrations, exposure
  scenarios, or regulatory thresholds.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient, IngredientConcern
from app.models.product import Product, ProductIngredient

# Increment this string whenever the scoring algorithm changes.
ANALYSIS_VERSION = "v1.0"


def _get_ingredient_concerns(
    ingredient: Ingredient, db: Session
) -> List[Dict[str, Any]]:
    """Return a list of concern dictionaries for a given ingredient.

    Each concern includes the ``source_name`` (where the evidence originated),
    ``level`` (e.g. ``high``, ``moderate``) and any additional ``details``.
    """
    concerns = (
        db.query(IngredientConcern)
        .filter(IngredientConcern.ingredient_id == ingredient.id)
        .all()
    )
    return [
        {
            "source_name": c.source_name,
            "level": c.level,
            "details": c.extra_data,
        }
        for c in concerns
    ]


def compute_product_risk(product: Product, db: Session) -> Dict[str, Any]:
    """Compute an explainable risk assessment for a ``Product``.

    The function gathers raw OCR‑derived ingredient entries (``ProductIngredient``)
    and, where possible, resolves them to a canonical ``Ingredient``.  For each
    ingredient we expose:

    * ``ingredient_id`` – the FK to the canonical record (may be ``None``).
    * ``raw_name`` – the raw text from the scan.
    * ``hazard_score`` – the stored numeric hazard indicator (or ``None``).
    * ``concerns`` – a list of documented concerns with provenance.
    * ``missing_data`` – a boolean flag indicating whether any required field
      (hazard score or concerns) was unavailable.

    The overall ``product_risk_score`` is calculated as the arithmetic mean of
    all available ``hazard_score`` values.  If *any* ingredient is missing a
    hazard score, the overall score is set to ``None`` to signal indeterminate
    risk.

    The returned dictionary is ready to be serialised by a FastAPI response
    model.
    """
    ingredient_findings: List[Dict[str, Any]] = []
    hazard_scores: List[float] = []
    indeterminate = False

    for pi in product.product_ingredients:
        ingredient_data: Dict[str, Any] = {
            "product_ingredient_id": pi.id,
            "raw_name": pi.raw_name,
            "position": pi.position,
            "match_method": pi.match_method,
            "match_confidence": pi.match_confidence,
            "ingredient_id": pi.ingredient_id,
            "hazard_score": None,
            "concerns": [],
            "missing_data": False,
        }

        if pi.ingredient_id is not None:
            ingredient = (
                db.query(Ingredient).filter(Ingredient.id == pi.ingredient_id).first()
            )
            if ingredient:
                hazard = ingredient.hazard_score
                ingredient_data["hazard_score"] = hazard
                if hazard is not None:
                    hazard_scores.append(hazard)
                else:
                    indeterminate = True
                # Gather concerns for the canonical ingredient
                ingredient_data["concerns"] = _get_ingredient_concerns(ingredient, db)
                if not ingredient_data["concerns"]:
                    # No concerns recorded – still valid evidence, not flagged as missing.
                    pass
            else:
                # FK points to a non‑existent ingredient – treat as missing data.
                ingredient_data["missing_data"] = True
                indeterminate = True
        else:
            # No canonical link – we cannot assess hazard.
            ingredient_data["missing_data"] = True
            indeterminate = True

        # If we have no hazard score or concerns, mark missing data.
        if ingredient_data["hazard_score"] is None:
            ingredient_data["missing_data"] = True

        ingredient_findings.append(ingredient_data)

    product_risk_score: Optional[float] = None
    if not indeterminate and hazard_scores:
        product_risk_score = sum(hazard_scores) / len(hazard_scores)

    return {
        "product_id": product.id,
        "analysis_version": ANALYSIS_VERSION,
        "product_risk_score": product_risk_score,
        "ingredient_findings": ingredient_findings,
        "explanation": (
            "Risk is the mean of available hazard scores. "
            "If any ingredient lacks a hazard score, the overall risk is "
            "considered indeterminate (null)."
        ),
    }


