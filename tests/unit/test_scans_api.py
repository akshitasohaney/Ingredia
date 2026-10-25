"""Tests for the OCR scan upload and ingredient confirmation endpoints.

These tests use the in‑memory SQLite database provided by the `client` fixture
in `tests/conftest.py`. They monkey‑patch the OCR extractor so the suite does
not depend on an actual Tesseract installation.
"""

import io
import os
import uuid
import pytest

from fastapi.testclient import TestClient

# The `client` fixture yields a TestClient with the test DB injected.

@pytest.fixture
def png_bytes() -> bytes:
    """Return a minimal valid PNG binary (1x1 pixel)."""
    # PNG header for a 1×1 transparent pixel
    return (
        b"\x89PNG\r\n\x1a\n"  # signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk
        b"\x00\x00\x00\x01\x00\x00\x00\x01"  # 1x1 size
        b"\x08\x06\x00\x00\x00"  # RGBA
        b"\x1f\x15\xc4\x89"  # CRC
        b"\x00\x00\x00\x0aIDATx\x9c\x63\x60\x00\x00\x00\x02\x00\x01"  # IDAT
        b"\x0d\x0a\x2d\xb4"  # CRC
        b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND
    )

def test_upload_valid_image(monkeypatch, client: TestClient, png_bytes: bytes):
    """Successful upload returns OCR text, confidence and match details."""

    # Mock OCR extractor to return deterministic values
    def fake_extract_text(_path):
        return "Water, Glycerin", {"Water": 95, "Glycerin": 90}

    monkeypatch.setattr("app.ocr.extractor.extract_text", fake_extract_text)

    files = {"file": ("test.png", png_bytes, "image/png")}
    response = client.post("/scans/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data
    assert data["ocr_text"] == "Water, Glycerin"
    # Average confidence of 92.5
    assert abs(data["ocr_confidence"] - 92.5) < 0.01
    # Match section must be present
    match = data["match"]
    assert match["token_count"] == 2
    # With an empty DB both tokens are unresolved
    assert match["unresolved"] == 2

def test_upload_invalid_extension(monkeypatch, client: TestClient):
    files = {"file": ("bad.txt", b"not an image", "text/plain")}
    response = client.post("/scans/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]

def test_upload_oversized_file(monkeypatch, client: TestClient):
    # Create a >5 MiB payload (5 MiB + 1 byte)
    big_content = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.png", big_content, "image/png")}
    response = client.post("/scans/upload", files=files)
    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]

def test_upload_ocr_failure(monkeypatch, client: TestClient, png_bytes: bytes):
    def failing_extract(_path):
        raise RuntimeError("Tesseract missing")
    monkeypatch.setattr("app.ocr.extractor.extract_text", failing_extract)
    files = {"file": ("test.png", png_bytes, "image/png")}
    response = client.post("/scans/upload", files=files)
    assert response.status_code == 500
    assert "Tesseract missing" in response.json()["detail"]

def test_confirm_success(monkeypatch, client: TestClient, png_bytes: bytes):
    # Mock OCR to produce two tokens
    monkeypatch.setattr(
        "app.ocr.extractor.extract_text",
        lambda _path: ("Water, Glycerin", {"Water": 95, "Glycerin": 90}),
    )
    upload = client.post("/scans/upload", files={"file": ("test.png", png_bytes, "image/png")})
    assert upload.status_code == 200
    scan_id = upload.json()["scan_id"]
    # Confirm both tokens as accepted
    payload = {
        "items": [
            {"raw_token": "Water", "user_accepted": True},
            {"raw_token": "Glycerin", "user_accepted": True},
        ]
    }
    confirm = client.patch(f"/scans/confirm/{scan_id}", json=payload)
    assert confirm.status_code == 200
    data = confirm.json()
    assert data["scan_id"] == scan_id
    assert data["updated"] == 2
    assert data["status"] == "user_confirmed"

def test_confirm_invalid_id(client: TestClient):
    payload = {"items": []}
    resp = client.patch("/scans/confirm/9999", json=payload)
    assert resp.status_code == 404
    assert "Scan not found" in resp.json()["detail"]

def test_confirm_malformed_request(client: TestClient, png_bytes: bytes, monkeypatch):
    monkeypatch.setattr(
        "app.ocr.extractor.extract_text",
        lambda _path: ("Water", {"Water": 95}),
    )
    upload = client.post("/scans/upload", files={"file": ("test.png", png_bytes, "image/png")})
    scan_id = upload.json()["scan_id"]
    # Missing required `items` field
    resp = client.patch(f"/scans/confirm/{scan_id}", json={})
    assert resp.status_code == 422  # FastAPI validation error

def test_fuzzy_match_not_auto_confirmed(monkeypatch, client: TestClient, png_bytes: bytes):
    # Setup a scenario where the matcher would return a fuzzy result.
    # We inject a fake linker that yields a fuzzy match for a known token.
    class FakeResult:
        def __init__(self, raw, norm, ing_id, method, conf, fuzzy_cands):
            self.raw_token = raw
            self.normalized_token = norm
            self.ingredient_id = ing_id
            self.match_method = method
            self.match_confidence = conf
            self.fuzzy_candidates = fuzzy_cands
    def fake_match_raw_text(_text, _linker):
        # One exact, one fuzzy
        return [
            FakeResult("Water", "water", 1, "exact", 1.0, []),
            FakeResult("FooBar", "foobar", None, "fuzzy", 0.6, []),
        ]
    monkeypatch.setattr("app.services.matching_service.match_raw_text", fake_match_raw_text)
    monkeypatch.setattr(
        "app.ocr.extractor.extract_text",
        lambda _path: ("Water FooBar", {"Water": 95, "FooBar": 80}),
    )
    upload = client.post("/scans/upload", files={"file": ("test.png", png_bytes, "image/png")})
    assert upload.status_code == 200
    data = upload.json()
    match = data["match"]
    # Ensure fuzzy suggestion count is reported
    assert match["fuzzy_suggestions"] == 1
    # Confirm endpoint should not auto‑accept the fuzzy token.
    scan_id = data["scan_id"]
    # Only accept the exact token; leave fuzzy untouched.
    payload = {
        "items": [
            {"raw_token": "Water", "user_accepted": True},
        ]
    }
    confirm = client.patch(f"/scans/confirm/{scan_id}", json=payload)
    assert confirm.status_code == 200
    # The status becomes confirmed even though one fuzzy token remains
    assert confirm.json()["status"] == "user_confirmed"
    # Verify that the fuzzy token still has user_accepted = None in DB
    # Direct DB query using the test session
    from app.database import SessionLocal
    from app.models.scan import ScanIngredient
    db = SessionLocal()
    fuzzy_row = (
        db.query(ScanIngredient)
        .filter(ScanIngredient.scan_id == scan_id, ScanIngredient.raw_token == "FooBar")
        .first()
    )
    assert fuzzy_row is not None
    assert fuzzy_row.user_accepted is None
    db.close()
