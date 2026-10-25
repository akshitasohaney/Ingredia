"""
Scans router — OCR scan lifecycle and ingredient-matching endpoints.

Endpoints:
    POST /api/v1/scans/match       — Match a raw ingredient text string (no DB write)
    POST /api/v1/scans/match/tokens — Match a pre-split token list (no DB write)

The scan workflow (upload → OCR → confirm → analyse) is planned for
Milestone 4; the matching endpoints are self-contained and usable now.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.nlp.ingredient_linker import IngredientLinker
from app.services.matching_service import (
    get_linker,
    link_results_to_dicts,
    match_raw_text,
    match_tokens,
)

router = APIRouter(prefix="/scans", tags=["scans"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FuzzyCandidate(BaseModel):
    ingredient_id: int
    canonical_name: str
    score: float
    match_method: str
    requires_review: bool


class MatchResultItem(BaseModel):
    raw_token: str
    normalized_token: str
    ingredient_id: int | None
    match_method: str
    match_confidence: float | None
    requires_review: bool
    fuzzy_candidates: list[FuzzyCandidate] = []


class RawTextMatchRequest(BaseModel):
    text: str = Field(
        ...,
        description=(
            "Raw ingredient label text, e.g. "
            "'Water, Glycerin, Niacinamide (Vitamin B3), Panthenol'."
        ),
        min_length=1,
    )


class TokenListMatchRequest(BaseModel):
    tokens: list[str] = Field(
        ...,
        description="Pre-split ingredient token list.",
        min_length=1,
    )


class MatchResponse(BaseModel):
    token_count: int
    matched: int          # exact or alias
    fuzzy_suggestions: int
    unresolved: int
    results: list[MatchResultItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(raw_results: list[Any]) -> MatchResponse:
    dicts = link_results_to_dicts(raw_results)
    items = [MatchResultItem(**d) for d in dicts]
    matched = sum(1 for i in items if i.match_method in ("exact", "alias"))
    fuzzy = sum(1 for i in items if i.match_method == "fuzzy")
    unresolved = sum(1 for i in items if i.match_method == "unresolved")
    return MatchResponse(
        token_count=len(items),
        matched=matched,
        fuzzy_suggestions=fuzzy,
        unresolved=unresolved,
        results=items,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/match", response_model=MatchResponse)
def match_raw(
    payload: RawTextMatchRequest,
    linker: IngredientLinker = Depends(get_linker),
):
    """
    Normalize, split, and match a raw ingredient label string.

    Returns one result per token with match method, confidence, and fuzzy
    suggestions for tokens that require review.
    """
    results = match_raw_text(payload.text, linker)
    return _build_response(results)


@router.post("/match/tokens", response_model=MatchResponse)
def match_token_list(
    payload: TokenListMatchRequest,
    linker: IngredientLinker = Depends(get_linker),
):
    """
    Match a caller-supplied list of pre-split ingredient tokens.

    Useful when the caller has already tokenized the label text.
    """
    results = match_tokens(payload.tokens, linker)
    return _build_response(results)
