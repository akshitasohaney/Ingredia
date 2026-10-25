"""
fuzzy_matcher.py — rapidfuzz-based fuzzy matching for ingredient tokens.

Used only when exact and alias lookups fail.  Results are always tagged as
``match_method="fuzzy"`` and require human review before being accepted.

The matcher works against the same normalized canonical-name vocabulary
used by SynonymIndex so there is no duplication of DB loading logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import process as rf_process
from rapidfuzz.distance import JaroWinkler


@dataclass(slots=True, frozen=True)
class FuzzyMatch:
    """A single fuzzy-match suggestion."""

    ingredient_id: int
    canonical_name: str
    score: float          # 0.0–1.0 (JaroWinkler similarity)
    match_method: str = "fuzzy"
    requires_review: bool = True


class FuzzyMatcher:
    """
    Wraps rapidfuzz to find the closest ingredient(s) for a token.

    Parameters
    ----------
    vocabulary:
        Mapping of normalized canonical name -> ingredient_id.
        Typically ``SynonymIndex.exact``.
    auto_accept_threshold:
        Score >= this is included but still *requires review* (no
        auto-promotion is done here; that is the caller's responsibility).
    suggest_threshold:
        Minimum score for a match to be surfaced at all.
    top_k:
        Maximum number of candidates to return.
    """

    def __init__(
        self,
        vocabulary: dict[str, int],
        auto_accept_threshold: float = 0.95,
        suggest_threshold: float = 0.85,
        top_k: int = 3,
    ) -> None:
        self._vocab = vocabulary           # normalized_name -> ingredient_id
        self._choices = list(vocabulary.keys())
        self._auto_accept_threshold = auto_accept_threshold
        self._suggest_threshold = suggest_threshold
        self._top_k = top_k

    def match(self, token: str) -> list[FuzzyMatch]:
        """
        Return up to ``top_k`` fuzzy suggestions for *token*.

        Only candidates with score >= ``suggest_threshold`` are returned.
        The list is sorted descending by score.
        """
        if not token or not self._choices:
            return []

        normalized_token = token.strip().lower()

        # Use JaroWinkler — better for ingredient names (prefix-sensitive, short strings)
        results = rf_process.extract(
            normalized_token,
            self._choices,
            scorer=JaroWinkler.normalized_similarity,
            limit=self._top_k,
            score_cutoff=self._suggest_threshold,
        )

        matches: list[FuzzyMatch] = []
        for name, score, _ in results:
            ingredient_id = self._vocab.get(name)
            if ingredient_id is None:
                continue
            matches.append(
                FuzzyMatch(
                    ingredient_id=ingredient_id,
                    canonical_name=name,
                    score=round(score, 4),
                )
            )

        return matches

    def best(self, token: str) -> FuzzyMatch | None:
        """Return the single best match, or None if below threshold."""
        candidates = self.match(token)
        return candidates[0] if candidates else None
