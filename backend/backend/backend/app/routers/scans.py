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

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from pathlib import Path
import uuid
import shutil
from pydantic import BaseModel, Field

from app.nlp.ingredient_linker import IngredientLinker
from app.services.matching_service import (
    get_linker,
    link_results_to_dicts,
    match_raw_text,
    match_tokens,
)
from app.ocr.preprocessor import preprocess_image
from app.ocr.extractor import extract_text
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter(prefix="/scans", tags=["scans"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    scan_id: int
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    match: MatchResponse

class ConfirmItem(BaseModel):
    raw_token: str
    ingredient_id: int | None = None
    user_accepted: bool
    corrected_token: str | None = None

class ConfirmRequest(BaseModel):
    items: list[ConfirmItem]

class ConfirmResponse(BaseModel):
    scan_id: int
    updated: int
    status: str



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


@router.post("/upload", response_model=UploadResponse)
async def upload_scan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    linker: IngredientLinker = Depends(get_linker),
):
    """Upload an ingredient-label image, run OCR, and return match results.

    The image is saved under `uploads/` with a UUID filename. Supported
    extensions are .jpg, .jpeg, .png. Size limit is 5 MiB.
    """
    # Validate content type / extension
    allowed_ext = {".jpg", ".jpeg", ".png"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: jpg, jpeg, png",
        )
    MAX_SIZE = 5 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Max 5 MiB.",
        )
    # Save to disk safely
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    safe_name = f"{uuid.uuid4()}{suffix}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(contents)
    # Preprocess image
    try:
        preprocessed_path = preprocess_image(file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image preprocessing failed: {exc}",
        )
    # OCR extraction
    try:
        ocr_text, confidence_map = extract_text(preprocessed_path)
    except RuntimeError as exc:
        # Missing Tesseract or OCR failure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    # Compute average confidence if available
    avg_confidence = None
    if confidence_map:
        avg_confidence = sum(confidence_map.values()) / len(confidence_map)
    # Create Scan DB entry
    from app.models.scan import Scan, ScanIngredient
    scan = Scan(
        image_path=str(file_path),
        ocr_raw_text=ocr_text,
        ocr_confidence=avg_confidence,
        review_status="pending_review",
    )
    db.add(scan)
    db.flush()  # obtain scan.id
    # Run matching pipeline on OCR text
    raw_results = match_raw_text(ocr_text or "", linker)
    # Populate ScanIngredient rows
    for res in raw_results:
        si = ScanIngredient(
            scan_id=scan.id,
            raw_token=res.raw_token,
            normalized_token=res.normalized_token,
            candidate_ingredient_id=res.ingredient_id,
            match_confidence=res.match_confidence,
            user_accepted=None,
        )
        db.add(si)
    db.commit()
    # Build response using existing helper
    match_resp = _build_response(raw_results)
    return UploadResponse(
        scan_id=scan.id,
        ocr_text=ocr_text,
        ocr_confidence=avg_confidence,
        match=match_resp,
    )


@router.patch("/confirm/{scan_id}", response_model=ConfirmResponse)
def confirm_scan(
    scan_id: int,
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
    linker: IngredientLinker = Depends(get_linker),
):
    """Accept or reject ingredient matches for a given scan.

    The client sends a list of ConfirmItem objects. Each item updates the
    corresponding ScanIngredient row (matched by raw_token). After all
    items are processed the Scan.review_status moves to 'user_confirmed'.
    """
    from app.models.scan import Scan, ScanIngredient
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.review_status not in {"pending_review", "user_edited"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm scan in status {scan.review_status}",
        )
    updated = 0
    for item in payload.items:
        si = (
            db.query(ScanIngredient)
            .filter(
                ScanIngredient.scan_id == scan_id,
                ScanIngredient.raw_token == item.raw_token,
            )
            .first()
        )
        if not si:
            continue
        si.user_accepted = item.user_accepted
        if item.ingredient_id is not None:
            si.candidate_ingredient_id = item.ingredient_id
        if item.corrected_token:
            si.raw_token = item.corrected_token
        updated += 1
    # Update status if at least one item processed
    if updated:
        scan.review_status = "user_confirmed"
        db.add(scan)
    db.commit()
    return ConfirmResponse(scan_id=scan.id, updated=updated, status=scan.review_status)

