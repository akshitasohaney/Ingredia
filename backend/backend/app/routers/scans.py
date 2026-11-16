"""
Scans router – POST/GET /api/v1/scans

OCR pipeline:
1. Upload image → pytesseract extracts text
2. Text is split into ingredient tokens
3. Each token is fuzzy-matched against the ingredients table (rapidfuzz)
4. User can review/accept/reject each match
5. Accepted matches drive the analysis
"""
import os
import re
import io
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.models.scan import Scan, ScanIngredient
from app.models.ingredient import Ingredient
from app.schemas.schemas import (
    IngredientRisk,
    RiskAnalysis,
    ScanRead,
    ScanListItem,
    ScanTextSubmit,
    ScanIngredientPatch,
)
from app.config import get_settings

router = APIRouter(prefix="/scans", tags=["scans"])

# ── Upload directory ──────────────────────────────────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── OCR helpers ───────────────────────────────────────────────────────────────

OCR_UNAVAILABLE = False  # set to True once we detect tesseract is missing

def _run_ocr(image_bytes: bytes) -> tuple[str, float, str | None]:
    """
    Run pytesseract OCR on image bytes.
    Returns (text, confidence 0-1, error_message|None).
    Never raises — on failure returns ('', 0.0, reason).
    """
    global OCR_UNAVAILABLE
    try:
        import pytesseract
        from PIL import Image

        # Windows installers do not always update the PATH of an already
        # running server. Honour an explicit setting and otherwise recognise
        # the standard Tesseract installation location.
        configured_cmd = os.getenv("TESSERACT_CMD")
        default_windows_cmd = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if configured_cmd:
            pytesseract.pytesseract.tesseract_cmd = configured_cmd
        elif default_windows_cmd.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(default_windows_cmd)

        img = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) >= 0]
        avg_conf = (sum(confidences) / len(confidences) / 100) if confidences else 0.0
        text = pytesseract.image_to_string(img)
        return text, round(avg_conf, 3), None
    except Exception as exc:
        err = str(exc)
        if "tesseract" in err.lower() or "not installed" in err.lower() or "PATH" in err:
            OCR_UNAVAILABLE = True
            return (
                "",
                0.0,
                "Tesseract OCR is not installed on this server. "
                "Please use the 'Paste text' option to enter the ingredient list manually.",
            )
        return "", 0.0, f"OCR error: {exc}"


def _tokenize_ingredients(raw_text: str) -> list[str]:
    """
    Split OCR text into ingredient tokens.
    Ingredient lists are comma-separated; we also strip parenthetical comments.
    """
    # Remove line-breaks, collapse whitespace
    text = re.sub(r"[\r\n]+", " ", raw_text)
    # Split standard label separators. Ampersand-separated ingredients are
    # separate INCI entries too (for example "Dimethicone & Dimethiconol").
    parts = re.split(r"[,;]|\s+(?:&|and)\s+", text, flags=re.IGNORECASE)
    tokens = []
    for p in parts:
        p = p.strip()
        # OCR often preserves the label heading in the first token.
        p = re.sub(r"^ingredients?\s*:\s*", "", p, flags=re.IGNORECASE).strip()
        # Remove standalone numbers / percent signs / brackets
        p = re.sub(r"\([^)]*\)", "", p).strip()
        p = re.sub(r"\s+", " ", p)
        if 2 <= len(p) <= 120:
            tokens.append(p)
    return tokens


def _fuzzy_match_ingredient(token: str, db: Session, settings) -> tuple[Optional[Ingredient], float]:
    """
    Fuzzy-match a token against the ingredients table using rapidfuzz.
    Returns (best Ingredient or None, confidence 0-1).
    """
    from rapidfuzz import fuzz, process as rfprocess

    all_ingredients = db.query(Ingredient).all()
    if not all_ingredients:
        return None, 0.0

    # Build a mapping: display_string → ingredient
    choices: dict[str, Ingredient] = {}
    for ing in all_ingredients:
        choices[ing.name.lower()] = ing
        if ing.inci_name:
            choices[ing.inci_name.lower()] = ing
        if ing.aliases:
            for alias in ing.aliases.split(","):
                alias = alias.strip().lower()
                if alias:
                    choices[alias] = ing

    token_lower = token.lower()
    result = rfprocess.extractOne(token_lower, list(choices.keys()), scorer=fuzz.token_sort_ratio)
    if result is None:
        return None, 0.0

    best_key, score, _ = result
    confidence = round(score / 100, 3)

    if confidence >= settings.fuzzy_suggest_threshold:
        return choices[best_key], confidence
    return None, confidence


def _build_scan_ingredients(scan: Scan, tokens: list[str], db: Session) -> None:
    """Create ScanIngredient rows from OCR tokens."""
    settings = get_settings()
    for token in tokens:
        best_ing, conf = _fuzzy_match_ingredient(token, db, settings)
        si = ScanIngredient(
            scan_id=scan.id,
            raw_token=token,
            normalized_token=token.strip().title() if not best_ing else best_ing.name,
            candidate_ingredient_id=best_ing.id if best_ing else None,
            match_confidence=conf if best_ing else None,
            # Exact / very high-confidence matches are safe to include by
            # default. Lower-confidence matches still require a decision.
            user_accepted=True if best_ing and conf >= settings.fuzzy_auto_accept_threshold else None,
        )
        db.add(si)


def _load_scan_detail(scan_id: int, db: Session) -> Scan:
    scan = (
        db.query(Scan)
        .options(
            joinedload(Scan.scan_ingredients).joinedload(ScanIngredient.ingredient)
        )
        .filter(Scan.id == scan_id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=ScanRead, status_code=201)
async def upload_scan(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a label image. Runs OCR, tokenises the ingredient list,
    and fuzzy-matches each token against the ingredient database.
    Returns a Scan with `scan_ingredients` pending user review.
    """
    # Validate mime type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=413, detail="Image too large (max 20 MB).")

    # Save to disk
    ext = Path(file.filename or "upload").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / filename
    save_path.write_bytes(image_bytes)

    # OCR – never raises; returns (text, confidence, error_message|None)
    raw_text, ocr_confidence, ocr_error = _run_ocr(image_bytes)

    # Persist scan record
    review_status = "ocr_failed" if ocr_error else "pending_review"
    scan = Scan(
        image_path=str(save_path),
        ocr_raw_text=raw_text or ocr_error,   # store error message as raw text so FE can display it
        ocr_confidence=ocr_confidence,
        review_status=review_status,
    )
    db.add(scan)
    db.flush()  # get scan.id

    # Only tokenise if we got text
    if raw_text:
        tokens = _tokenize_ingredients(raw_text)
        _build_scan_ingredients(scan, tokens, db)

    db.commit()
    return _load_scan_detail(scan.id, db)


@router.post("/text", response_model=ScanRead, status_code=201)
def submit_scan_text(body: ScanTextSubmit, db: Session = Depends(get_db)):
    """
    Submit raw ingredient text manually (copy-paste fallback).
    Tokenises and matches the same way as image upload.
    """
    # Save text as a fake "path" for uniformity
    filename = f"{uuid.uuid4().hex}.txt"
    save_path = UPLOAD_DIR / filename
    save_path.write_text(body.text, encoding="utf-8")

    scan = Scan(
        image_path=str(save_path),
        ocr_raw_text=body.text,
        ocr_confidence=1.0,  # text is exact — no OCR uncertainty
        review_status="pending_review",
    )
    db.add(scan)
    db.flush()

    tokens = _tokenize_ingredients(body.text)
    _build_scan_ingredients(scan, tokens, db)

    db.commit()
    return _load_scan_detail(scan.id, db)


@router.get("", response_model=list[ScanListItem])
def list_scans(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List scans with pagination, newest first."""
    return (
        db.query(Scan)
        .order_by(Scan.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{scan_id}", response_model=ScanRead)
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """Return full scan detail including matched ingredients."""
    return _load_scan_detail(scan_id, db)


@router.patch("/{scan_id}/ingredients/{si_id}", response_model=ScanRead)
def patch_scan_ingredient(
    scan_id: int,
    si_id: int,
    body: ScanIngredientPatch,
    db: Session = Depends(get_db),
):
    """Accept or reject a single OCR-matched ingredient token."""
    si = (
        db.query(ScanIngredient)
        .filter(ScanIngredient.id == si_id, ScanIngredient.scan_id == scan_id)
        .first()
    )
    if not si:
        raise HTTPException(status_code=404, detail="ScanIngredient not found.")
    si.user_accepted = body.user_accepted
    db.commit()
    return _load_scan_detail(scan_id, db)


@router.post("/{scan_id}/confirm", response_model=ScanRead)
def confirm_scan(scan_id: int, db: Session = Depends(get_db)):
    """Mark a scan as user-confirmed (all reviews done)."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    scan.review_status = "user_confirmed"
    db.commit()
    return _load_scan_detail(scan_id, db)


@router.get("/{scan_id}/analysis", response_model=RiskAnalysis)
def get_scan_analysis(scan_id: int, db: Session = Depends(get_db)):
    """Analyse every accepted ingredient from a confirmed scan."""
    scan = _load_scan_detail(scan_id, db)
    accepted = [item for item in scan.scan_ingredients if item.user_accepted is True]

    if not accepted:
        raise HTTPException(
            status_code=422,
            detail="Accept at least one matched ingredient before requesting analysis.",
        )

    risks: list[IngredientRisk] = []
    for item in accepted:
        if item.ingredient is None:
            # Keep an accepted, not-yet-catalogued token visible in the final
            # report rather than silently dropping it. We do not invent a
            # safety conclusion where reference data is unavailable.
            risks.append(IngredientRisk(
                ingredient_id=-item.id,
                name=item.raw_token,
                function="Reference record pending",
                description="This label ingredient was included in your review, but is not yet in Ingredia's reference library.",
                evidence_summary="No ingredient-specific evidence summary is available yet. Check the spelling on the label or consult a qualified professional for personalised advice.",
                evidence_source="Ingredia reference library: record pending",
                confidence_score=0.0,
                is_concern=False,
                concern_reason=None,
            ))
            continue
        ing = item.ingredient
        is_concern = bool(ing.is_allergen or ing.caution_for)
        concern_reason = None
        if ing.is_allergen:
            concern_reason = "Potential allergen — may cause reactions in sensitised individuals."
        elif ing.caution_for:
            concern_reason = f"Caution advised for: {ing.caution_for}"

        risks.append(IngredientRisk(
            ingredient_id=ing.id,
            name=ing.name,
            function=ing.function,
            description=ing.description,
            evidence_summary=ing.evidence_summary,
            evidence_source=ing.evidence_source,
            confidence_score=ing.confidence_score,
            suitable_for=ing.suitable_for,
            caution_for=ing.caution_for,
            is_fragrance=bool(ing.is_fragrance),
            is_allergen=bool(ing.is_allergen),
            is_concern=is_concern,
            concern_reason=concern_reason,
        ))

    return RiskAnalysis(
        product_id=scan.id,
        product_name="Scanned ingredient list",
        ingredient_count=len(risks),
        unidentified_count=sum(
            1 for item in scan.scan_ingredients
            if item.user_accepted is True and item.candidate_ingredient_id is None
        ),
        ingredients=risks,
    )
