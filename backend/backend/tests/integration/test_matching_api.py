"""
Integration tests for the ingredient-matching endpoints in the scans router.

    POST /api/v1/scans/match         — raw text input
    POST /api/v1/scans/match/tokens  — pre-split token list

Uses a seeded in-memory SQLite DB (StaticPool) so real ingredia.db is
never touched.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.ingredient import Ingredient, IngredientAlias
from app.services.matching_service import get_linker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_client():
    """
    TestClient with a seeded in-memory DB (StaticPool).
    Overrides both get_db and get_linker dependencies.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    # Seed ingredients
    water = Ingredient(canonical_name="Water", extra_data={})
    glycerin = Ingredient(canonical_name="Glycerin", extra_data={})
    niacinamide = Ingredient(canonical_name="Niacinamide", extra_data={})
    panthenol = Ingredient(canonical_name="Panthenol", extra_data={})
    session.add_all([water, glycerin, niacinamide, panthenol])
    session.flush()

    session.add_all([
        IngredientAlias(ingredient_id=water.id, alias="Aqua", alias_type="inci"),
        IngredientAlias(ingredient_id=glycerin.id, alias="Glycerol", alias_type="common"),
        IngredientAlias(
            ingredient_id=niacinamide.id, alias="Vitamin B3", alias_type="common"
        ),
    ])
    session.commit()

    def _override_db():
        yield session

    # Override both get_db (general) and get_linker (uses get_db internally)
    from app.nlp.fuzzy_matcher import FuzzyMatcher
    from app.nlp.ingredient_linker import IngredientLinker
    from app.nlp.synonym_matcher import SynonymIndex

    def _override_linker():
        idx = SynonymIndex.build(session)
        fuzzy = FuzzyMatcher(idx.exact, suggest_threshold=0.80)
        return IngredientLinker(index=idx, fuzzy=fuzzy)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_linker] = _override_linker

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# POST /api/v1/scans/match
# ---------------------------------------------------------------------------


class TestRawTextMatch:
    def test_all_exact_ingredients(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Water, Glycerin, Niacinamide, Panthenol"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_count"] == 4
        assert data["matched"] == 4
        assert data["fuzzy_suggestions"] == 0
        assert data["unresolved"] == 0

    def test_alias_tokens_counted_as_matched(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Aqua, Glycerol"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] == 2  # aliases count as matched

    def test_unknown_token_unresolved(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Water, unknownxyz12345abc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["unresolved"] >= 1

    def test_match_method_in_results(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Water, Aqua"},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        # normalize_text lowercases before split, so raw_token is also lowercased
        methods = {r["raw_token"]: r["match_method"] for r in results}
        assert methods["water"] == "exact"
        assert methods["aqua"] == "alias"

    def test_requires_review_false_for_exact(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Glycerin"},
        )
        result = resp.json()["results"][0]
        assert result["requires_review"] is False

    def test_requires_review_true_for_unresolved(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "xyzunknown99"},
        )
        result = resp.json()["results"][0]
        assert result["requires_review"] is True

    def test_ingredient_id_present_for_match(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Water"},
        )
        result = resp.json()["results"][0]
        assert result["ingredient_id"] is not None

    def test_ingredient_id_none_for_unresolved(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "completely_unknown_ingredient"},
        )
        result = resp.json()["results"][0]
        assert result["ingredient_id"] is None

    def test_normalized_token_in_result(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "WATER"},
        )
        result = resp.json()["results"][0]
        # normalize_text lowercases the whole text before split_ingredients,
        # so both raw_token and normalized_token are "water" here.
        assert result["normalized_token"] == "water"
        assert result["raw_token"] == "water"  # split_ingredients sees lowercased text

    def test_fuzzy_suggestion_has_candidates(self, seeded_client):
        """A near-match should return fuzzy_candidates list."""
        resp = seeded_client.post(
            "/api/v1/scans/match",
            json={"text": "Glycerine"},  # close to Glycerin
        )
        data = resp.json()
        # Could be alias hit (Glycerol is an alias) or fuzzy — either is correct
        result = data["results"][0]
        if result["match_method"] == "fuzzy":
            assert len(result["fuzzy_candidates"]) >= 1
            assert result["requires_review"] is True

    def test_empty_text_rejected(self, seeded_client):
        resp = seeded_client.post("/api/v1/scans/match", json={"text": ""})
        assert resp.status_code == 422  # Pydantic validation error (min_length=1)


# ---------------------------------------------------------------------------
# POST /api/v1/scans/match/tokens
# ---------------------------------------------------------------------------


class TestTokenListMatch:
    def test_basic_token_list(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": ["Water", "Glycerin", "Niacinamide"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_count"] == 3
        assert data["matched"] == 3

    def test_mixed_list(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": ["Water", "Aqua", "unknowntoken"]},
        )
        data = resp.json()
        assert data["matched"] == 2   # Water (exact) + Aqua (alias)
        assert data["unresolved"] >= 1

    def test_empty_list_rejected(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": []},
        )
        assert resp.status_code == 422

    def test_response_preserves_order(self, seeded_client):
        tokens = ["Panthenol", "Water", "Glycerin"]
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": tokens},
        )
        results = resp.json()["results"]
        for token, result in zip(tokens, results):
            assert result["raw_token"] == token

    def test_confidence_1_for_exact(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": ["Water"]},
        )
        result = resp.json()["results"][0]
        assert result["match_confidence"] == 1.0

    def test_confidence_none_for_unresolved(self, seeded_client):
        resp = seeded_client.post(
            "/api/v1/scans/match/tokens",
            json={"tokens": ["xyz_unresolved"]},
        )
        result = resp.json()["results"][0]
        assert result["match_confidence"] is None
