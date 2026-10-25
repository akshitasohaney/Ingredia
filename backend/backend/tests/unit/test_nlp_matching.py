"""
Unit tests for app/nlp/synonym_matcher.py and app/nlp/fuzzy_matcher.py,
and integration tests for app/nlp/ingredient_linker.py.

All tests use an isolated in-memory SQLite DB via the shared `mem_db` fixture.
No real database is touched.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.ingredient import Ingredient, IngredientAlias
from app.nlp.fuzzy_matcher import FuzzyMatcher
from app.nlp.ingredient_linker import IngredientLinker, LinkResult
from app.nlp.synonym_matcher import SynonymIndex


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    # Seed a small vocabulary
    water = Ingredient(canonical_name="Water", extra_data={})
    glycerin = Ingredient(canonical_name="Glycerin", extra_data={})
    niacinamide = Ingredient(canonical_name="Niacinamide", extra_data={})
    panthenol = Ingredient(canonical_name="Panthenol", extra_data={})
    tocopherol = Ingredient(canonical_name="Tocopherol", extra_data={})
    session.add_all([water, glycerin, niacinamide, panthenol, tocopherol])
    session.flush()

    # Aliases
    session.add_all([
        IngredientAlias(ingredient_id=water.id, alias="Aqua", alias_type="inci"),
        IngredientAlias(ingredient_id=water.id, alias="WATER", alias_type="common"),
        IngredientAlias(ingredient_id=glycerin.id, alias="Glycerol", alias_type="common"),
        IngredientAlias(
            ingredient_id=niacinamide.id, alias="Vitamin B3", alias_type="common"
        ),
        IngredientAlias(
            ingredient_id=niacinamide.id, alias="Nicotinamide", alias_type="inci"
        ),
    ])
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# SynonymIndex tests
# ---------------------------------------------------------------------------


class TestSynonymIndex:
    def test_build_exact_keys(self, db):
        idx = SynonymIndex.build(db)
        # All canonical names should be in exact dict (lowercased)
        for name in ["water", "glycerin", "niacinamide", "panthenol", "tocopherol"]:
            assert name in idx.exact, f"{name!r} missing from exact index"

    def test_exact_lookup_hit(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("Water")
        assert method == "exact"
        assert ing_id is not None

    def test_exact_lookup_case_insensitive(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("WATER")
        # "WATER" is both an alias and a canonical name; exact wins
        assert method == "exact"
        assert ing_id is not None

    def test_alias_lookup_hit(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("Aqua")
        assert method == "alias"
        # Aqua should resolve to Water's id
        water_id = idx.exact["water"]
        assert ing_id == water_id

    def test_alias_lookup_glycerol(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("Glycerol")
        assert method == "alias"
        glycerin_id = idx.exact["glycerin"]
        assert ing_id == glycerin_id

    def test_alias_vitamin_b3(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("Vitamin B3")
        assert method == "alias"
        niac_id = idx.exact["niacinamide"]
        assert ing_id == niac_id

    def test_miss_returns_none(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("totally_unknown_xyz")
        assert ing_id is None
        assert method is None

    def test_empty_string_returns_none(self, db):
        idx = SynonymIndex.build(db)
        ing_id, method = idx.lookup("")
        assert ing_id is None

    def test_exact_takes_priority_over_alias(self, db):
        """An alias that matches a canonical name should be superseded by exact."""
        idx = SynonymIndex.build(db)
        # "glycerin" is a canonical name AND could be an alias elsewhere
        ing_id, method = idx.lookup("glycerin")
        assert method == "exact"


# ---------------------------------------------------------------------------
# FuzzyMatcher tests
# ---------------------------------------------------------------------------


class TestFuzzyMatcher:
    def _make_vocab(self, db) -> dict[str, int]:
        idx = SynonymIndex.build(db)
        return idx.exact

    def test_close_match_returned(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab, suggest_threshold=0.80)
        result = fm.best("niacinamid")  # one char shorter
        assert result is not None
        assert result.canonical_name == "niacinamide"
        assert result.score >= 0.80

    def test_very_different_string_below_threshold(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab, suggest_threshold=0.85)
        result = fm.best("xylitol_completely_different")
        assert result is None

    def test_match_requires_review_flag(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab, suggest_threshold=0.80)
        result = fm.best("glycerine")   # close to "glycerin"
        assert result is not None
        assert result.requires_review is True
        assert result.match_method == "fuzzy"

    def test_top_k_limit(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab, suggest_threshold=0.70, top_k=2)
        results = fm.match("pant")   # "panthenol" should be in there
        assert len(results) <= 2

    def test_results_sorted_descending(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab, suggest_threshold=0.70, top_k=5)
        results = fm.match("glycer")
        if len(results) > 1:
            for a, b in zip(results, results[1:]):
                assert a.score >= b.score

    def test_empty_token_returns_empty(self, db):
        vocab = self._make_vocab(db)
        fm = FuzzyMatcher(vocab)
        assert fm.match("") == []

    def test_empty_vocab_returns_empty(self):
        fm = FuzzyMatcher({})
        assert fm.match("niacinamide") == []


# ---------------------------------------------------------------------------
# IngredientLinker (pipeline integration) tests
# ---------------------------------------------------------------------------


def _make_linker(db, suggest_threshold: float = 0.85) -> IngredientLinker:
    idx = SynonymIndex.build(db)
    fuzzy = FuzzyMatcher(idx.exact, suggest_threshold=suggest_threshold)
    return IngredientLinker(index=idx, fuzzy=fuzzy)


class TestIngredientLinker:
    def test_exact_hit(self, db):
        linker = _make_linker(db)
        result = linker.link_token("Water")
        assert result.match_method == "exact"
        assert result.ingredient_id is not None
        assert result.requires_review is False
        assert result.match_confidence == 1.0

    def test_alias_hit(self, db):
        linker = _make_linker(db)
        result = linker.link_token("Aqua")
        assert result.match_method == "alias"
        assert result.requires_review is False
        assert result.match_confidence == 1.0

    def test_alias_nicotinamide(self, db):
        linker = _make_linker(db)
        result = linker.link_token("Nicotinamide")
        assert result.match_method == "alias"
        idx = SynonymIndex.build(db)
        assert result.ingredient_id == idx.exact["niacinamide"]

    def test_fuzzy_hit_requires_review(self, db):
        linker = _make_linker(db, suggest_threshold=0.80)
        result = linker.link_token("niacinamid")
        assert result.match_method == "fuzzy"
        assert result.requires_review is True
        assert result.match_confidence is not None
        assert 0.0 < result.match_confidence <= 1.0
        assert len(result.fuzzy_candidates) >= 1

    def test_unresolved_token(self, db):
        linker = _make_linker(db)
        result = linker.link_token("completelymadeupingredient99999")
        assert result.match_method == "unresolved"
        assert result.ingredient_id is None
        assert result.requires_review is True
        assert result.match_confidence is None
        assert result.fuzzy_candidates == []

    def test_normalized_token_stored(self, db):
        linker = _make_linker(db)
        result = linker.link_token("  WATER  ")
        assert result.normalized_token == "water"
        assert result.raw_token == "  WATER  "

    def test_link_tokens_preserves_order(self, db):
        linker = _make_linker(db)
        tokens = ["Water", "Glycerin", "Panthenol"]
        results = linker.link_tokens(tokens)
        assert len(results) == 3
        for raw, res in zip(tokens, results):
            assert res.raw_token == raw

    def test_link_tokens_empty(self, db):
        linker = _make_linker(db)
        assert linker.link_tokens([]) == []

    def test_exact_beats_alias_for_same_string(self, db):
        """A token matching both canonical name and an alias resolves as exact."""
        linker = _make_linker(db)
        # "water" is canonical AND there's an alias "WATER"
        result = linker.link_token("water")
        assert result.match_method == "exact"

    def test_full_pipeline_mixed_tokens(self, db):
        """Simulate a realistic ingredient list with different match types."""
        linker = _make_linker(db, suggest_threshold=0.80)
        tokens = [
            "Water",                        # exact
            "Aqua",                         # alias
            "niacinamid",                   # fuzzy (typo)
            "xylene_unknown_compound",      # unresolved
        ]
        results = linker.link_tokens(tokens)
        assert results[0].match_method == "exact"
        assert results[1].match_method == "alias"
        assert results[2].match_method == "fuzzy"
        assert results[3].match_method == "unresolved"
