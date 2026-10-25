"""
ingredient_linker.py — Orchestrates the three-tier matching pipeline.

Matching priority (per token):
    1. Exact match against canonical_name  → method="exact",   requires_review=False
    2. Alias match against ingredient_aliases → method="alias",   requires_review=False
    3. Fuzzy match (JaroWinkler, top-k)    → method="fuzzy",   requires_review=True
    4. No match found                       → method="unresolved", requires_review=True

The linker:
  - Normalises each raw token via ``normalizer.normalize_text``.
  - Returns one ``LinkResult`` per token; callers decide what to persist.
  - Is stateless between calls; all state lives in SynonymIndex / FuzzyMatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.nlp.fuzzy_matcher import FuzzyMatch, FuzzyMatcher
from app.nlp.normalizer import normalize_text
from app.nlp.synonym_matcher import SynonymIndex


@dataclass(slots=True)
class LinkResult:
    """
    The outcome of matching one raw ingredient token.

    Attributes
    ----------
    raw_token:
        The original string before any normalisation.
    normalized_token:
        Token after ``normalize_text()`` — the string actually compared.
    ingredient_id:
        Local DB primary key of the matched ingredient, or ``None``.
    match_method:
        One of ``"exact"`` | ``"alias"`` | ``"fuzzy"`` | ``"unresolved"``.
    match_confidence:
        Float 0–1 for fuzzy hits; ``1.0`` for exact/alias; ``None`` for unresolved.
    requires_review:
        ``True`` for fuzzy hits and unresolved tokens; ``False`` for exact/alias.
    fuzzy_candidates:
        All fuzzy suggestions (including the best one), ordered by score desc.
        Empty list for exact/alias/unresolved.
    """

    raw_token: str
    normalized_token: str
    ingredient_id: int | None = None
    match_method: str = "unresolved"
    match_confidence: float | None = None
    requires_review: bool = True
    fuzzy_candidates: list[FuzzyMatch] = field(default_factory=list)


class IngredientLinker:
    """
    Stateless ingredient linker.  Instantiate once per request (or cache it).

    Parameters
    ----------
    index:
        Pre-built SynonymIndex (exact + alias dicts).
    fuzzy:
        Pre-built FuzzyMatcher over the same vocabulary.
    """

    def __init__(self, index: SynonymIndex, fuzzy: FuzzyMatcher) -> None:
        self._index = index
        self._fuzzy = fuzzy

    def link_token(self, raw_token: str) -> LinkResult:
        """Match a single raw token through the three-tier pipeline."""
        normalized = normalize_text(raw_token)

        # Tier 1 & 2: exact / alias
        ingredient_id, method = self._index.lookup(normalized)
        if ingredient_id is not None:
            return LinkResult(
                raw_token=raw_token,
                normalized_token=normalized,
                ingredient_id=ingredient_id,
                match_method=method,      # "exact" or "alias"
                match_confidence=1.0,
                requires_review=False,
            )

        # Tier 3: fuzzy suggestions
        candidates = self._fuzzy.match(normalized)
        if candidates:
            best = candidates[0]
            return LinkResult(
                raw_token=raw_token,
                normalized_token=normalized,
                ingredient_id=best.ingredient_id,
                match_method="fuzzy",
                match_confidence=best.score,
                requires_review=True,
                fuzzy_candidates=candidates,
            )

        # Tier 4: no match
        return LinkResult(
            raw_token=raw_token,
            normalized_token=normalized,
            ingredient_id=None,
            match_method="unresolved",
            match_confidence=None,
            requires_review=True,
        )

    def link_tokens(self, raw_tokens: list[str]) -> list[LinkResult]:
        """Match a list of raw tokens, preserving order."""
        return [self.link_token(t) for t in raw_tokens]
