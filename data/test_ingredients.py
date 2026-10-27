import pytest
from fastapi import status
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientUpdate,
    IngredientConcernCreate,
)

# Helper data
base_ingredient = {
    "canonical_name": "TestIngredient",
    "cas_number": "123-45-6",
    "ec_number": "200-123-4",
    "function_tags": ["emollient", "preservative"],
    "hazard_score": 5.5,
    "hazard_basis": "in_vitro",
    "data_completeness": "complete",
    "ewg_score": 3,
    "eu_annex_status": "permitted",
}

concern_payload = {
    "concern_type": "carcinogen",
    "severity": "confirmed",
    "summary": "Potential carcinogenic effects observed in animal studies.",
    "source_name": "IARC",
    "source_url": "https://example.com/concern",
    "population_context": "occupational exposure",
}

def test_create_ingredient_success(client):
    response = client.post("/api/v1/ingredients/", json=base_ingredient)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["canonical_name"] == base_ingredient["canonical_name"]
    assert data["id"] is not None

def test_create_duplicate_ingredient_conflict(client):
    client.post("/api/v1/ingredients/", json=base_ingredient)
    response = client.post("/api/v1/ingredients/", json=base_ingredient)
    assert response.status_code == status.HTTP_409_CONFLICT

def test_get_ingredient_by_id(client):
    create_resp = client.post("/api/v1/ingredients/", json=base_ingredient)
    ingredient_id = create_resp.json()["id"]
    resp = client.get(f"/api/v1/ingredients/{ingredient_id}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == ingredient_id
    assert data["canonical_name"] == base_ingredient["canonical_name"]
    assert data["aliases"] == []
    assert data["concerns"] == []

def test_get_nonexistent_ingredient_404(client):
    resp = client.get("/api/v1/ingredients/99999")
    assert resp.status_code == status.HTTP_404_NOT_FOUND

def test_patch_ingredient_fields(client):
    create_resp = client.post("/api/v1/ingredients/", json=base_ingredient)
    ingredient_id = create_resp.json()["id"]
    patch_data = {"hazard_score": 7.2, "data_completeness": "partial"}
    resp = client.patch(f"/api/v1/ingredients/{ingredient_id}", json=patch_data)
    assert resp.status_code == status.HTTP_200_OK
    updated = resp.json()
    assert updated["hazard_score"] == 7.2
    assert updated["data_completeness"] == "partial"

def test_concern_crud_flow(client):
    create_resp = client.post("/api/v1/ingredients/", json=base_ingredient)
    ingredient_id = create_resp.json()["id"]
    resp = client.post(
        f"/api/v1/ingredients/{ingredient_id}/concerns",
        json=concern_payload,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    concern = resp.json()
    assert concern["concern_type"] == concern_payload["concern_type"]
    list_resp = client.get(f"/api/v1/ingredients/{ingredient_id}/concerns")
    assert list_resp.status_code == status.HTTP_200_OK
    concerns = list_resp.json()
    assert isinstance(concerns, list)
    assert any(c["id"] == concern["id"] for c in concerns)

def test_create_concern_missing_source_name_validation(client):
    create_resp = client.post("/api/v1/ingredients/", json=base_ingredient)
    ingredient_id = create_resp.json()["id"]
    bad_payload = {**concern_payload, "source_name": None}
    resp = client.post(
        f"/api/v1/ingredients/{ingredient_id}/concerns",
        json=bad_payload,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_delete_ingredient_cascade(client):
    create_resp = client.post("/api/v1/ingredients/", json=base_ingredient)
    ingredient_id = create_resp.json()["id"]
    client.post(
        f"/api/v1/ingredients/{ingredient_id}/concerns",
        json=concern_payload,
    )
    del_resp = client.delete(f"/api/v1/ingredients/{ingredient_id}")
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT
    get_resp = client.get(f"/api/v1/ingredients/{ingredient_id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
    concerns_resp = client.get(f"/api/v1/ingredients/{ingredient_id}/concerns")
    assert concerns_resp.status_code == status.HTTP_404_NOT_FOUND

def test_paginated_listing_and_filters(client):
    names = ["Alpha", "Beta", "Gamma", "Delta"]
    for name in names:
        payload = {**base_ingredient, "canonical_name": name}
        client.post("/api/v1/ingredients/", json=payload)
    resp = client.get("/api/v1/ingredients/?skip=0&limit=2")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 4
    assert len(data["items"]) == 2
    search_resp = client.get("/api/v1/ingredients/?search=Alph")
    assert search_resp.status_code == status.HTTP_200_OK
    items = search_resp.json()["items"]
    assert any(item["canonical_name"] == "Alpha" for item in items)
    range_resp = client.get("/api/v1/ingredients/?min_hazard=5&max_hazard=6")
    assert range_resp.status_code == status.HTTP_200_OK
    for item in range_resp.json()["items"]:
        assert 5 <= item["hazard_score"] <= 6
    comp_resp = client.get("/api/v1/ingredients/?data_completeness=complete")
    assert comp_resp.status_code == status.HTTP_200_OK
    for item in comp_resp.json()["items"]:
        assert item["data_completeness"] == "complete"
