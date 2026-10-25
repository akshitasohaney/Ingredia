"""
matching_service.py — FastAPI-friendly service for ingredient matching.

Provides:
  ``get_linker(db)``   — FastAPI dependency that returns a ready IngredientLinker.
  ``match_raw_text()`` — High-level helper: normalize + split + link a raw label.
  ``match_tokens()``   — Link a pre-split list of tokens.

The SynonymIndex and FuzzyMatcher are built once per request from the live
database.  For production scale these could be cached with a short TTL;
for Ingredia's current dataset size (~1 k ingredients) building per-request
is fast (<10 ms).

Usage in a route handler
------------------------
    from app.services.matching_service import get_linker, match_raw_text
    from app.database import get_db

    @router.post("/match")
    def match(payload: MatchRequest, db = Depends(get_db)):
        linker = get_linker(db)
        results = match_raw_text(payload.text, linker)
        return results
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.nlp.fuzzy_matcher import FuzzyMatcher
from app.nlp.ingredient_linker import IngredientLinker, LinkResult
from app.nlp.normalizer import process_raw
from app.nlp.synonym_matcher import SynonymIndex


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_linker(db: Session = Depends(get_db)) -> IngredientLinker:
    """
    FastAPI dependency: build and return an IngredientLinker for the current
    request using the provided DB session.

    The index is rebuilt every call (no cross-request cache).
    This is safe and sufficient for current dataset sizes.
    """
    settings = get_settings()
    index = SynonymIndex.build(db)
    fuzzy = FuzzyMatcher(
        vocabulary=index.exact,
        auto_accept_threshold=settings.fuzzy_auto_accept_threshold,
        suggest_threshold=settings.fuzzy_suggest_threshold,
    )
    return IngredientLinker(index=index, fuzzy=fuzzy)


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------


def match_raw_text(
    raw_text: str,
    linker: IngredientLinker,
) -> list[LinkResult]:
    """
    Normalize, split, and link all tokens in *raw_text*.

    Returns one LinkResult per token.
    Empty / whitespace-only tokens are skipped.
    """
    tokens = [t for t in process_raw(raw_text) if t.strip()]
    return linker.link_tokens(tokens)


def match_tokens(
    tokens: list[str],
    linker: IngredientLinker,
) -> list[LinkResult]:
    """Link a caller-provided token list (already split)."""
    return linker.link_tokens([t for t in tokens if t.strip()])


def link_results_to_dicts(results: list[LinkResult]) -> list[dict[str, Any]]:
    """
    Serialise LinkResult objects to plain dicts suitable for JSON responses.

    ``fuzzy_candidates`` is converted to a list of dicts; nested dataclasses
    are handled by ``dataclasses.asdict``.
    """
    return [asdict(r) for r in results]
