"""
synonym_matcher.py — DB-backed exact and alias matching.

Priority 1 (exact): canonical_name == normalized token (case-insensitive).
Priority 2 (alias): ingredient_aliases.alias == normalized token.

Returns the DB Ingredient id on a hit, None on a miss.
All lookups are O(1) against pre-built dicts loaded once per session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient, IngredientAlias

if TYPE_CHECKING:
    pass


@dataclass(slots=True, frozen=True)
class SynonymIndex:
    """
    In-memory index built from the database.

    ``exact``:  normalized(canonical_name) -> ingredient_id
    ``alias``:  normalized(alias)           -> ingredient_id

    Both keys are already normalized so callers only need to pass a
    normalized token.
    """

    exact: dict[str, int]
    alias: dict[str, int]

    @classmethod
    def build(cls, db: Session) -> "SynonymIndex":
        """Load all ingredients + aliases from *db* and build the index."""
        exact: dict[str, int] = {}
        alias: dict[str, int] = {}

        for ing in db.query(Ingredient).all():
            key = _norm(ing.canonical_name)
            if key:
                exact[key] = ing.id

        for al in db.query(IngredientAlias).all():
            key = _norm(al.alias)
            if key:
                # Alias resolves to its ingredient; do not overwrite an exact hit
                alias.setdefault(key, al.ingredient_id)

        return cls(exact=exact, alias=alias)

    def lookup(self, token: str) -> tuple[int | None, str | None]:
        """
        Look up a single (already normalized) token.

        Returns
        -------
        (ingredient_id, method)
            method is ``"exact"`` | ``"alias"`` | ``None``.
        """
        key = _norm(token)
        if not key:
            return None, None
        if key in self.exact:
            return self.exact[key], "exact"
        if key in self.alias:
            return self.alias[key], "alias"
        return None, None


def _norm(text: str | None) -> str:
    """Minimal normalisation for index keys: strip + lowercase."""
    if not text:
        return ""
    return text.strip().lower()
