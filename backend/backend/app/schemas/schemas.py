"""
Pydantic schemas for Ingredia API request/response models.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ─── Ingredient ──────────────────────────────────────────────────────────────

class IngredientBase(BaseModel):
    name: str
    inci_name: Optional[str] = None
    aliases: Optional[str] = None
    function: Optional[str] = None
    description: Optional[str] = None
    evidence_summary: Optional[str] = None
    evidence_source: Optional[str] = None
    confidence_score: Optional[float] = None
    suitable_for: Optional[str] = None
    caution_for: Optional[str] = None
    is_fragrance: bool = False
    is_allergen: bool = False


class IngredientRead(IngredientBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class IngredientSummary(BaseModel):
    """Lightweight ingredient summary used inside product/scan responses."""
    id: int
    name: str
    function: Optional[str] = None
    confidence_score: Optional[float] = None
    is_fragrance: bool = False
    is_allergen: bool = False
    model_config = ConfigDict(from_attributes=True)


# ─── Product ─────────────────────────────────────────────────────────────────

class ProductIngredientRead(BaseModel):
    id: int
    ingredient_id: int
    position: Optional[int] = None
    raw_name: Optional[str] = None
    ingredient: IngredientRead
    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    brand: Optional[str] = None
    product_type: Optional[str] = None
    intended_use: Optional[str] = None
    notes: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProductDetail(ProductBase):
    id: int
    product_ingredients: list[ProductIngredientRead] = []
    model_config = ConfigDict(from_attributes=True)


# ─── Analysis / Risk ─────────────────────────────────────────────────────────

class IngredientRisk(BaseModel):
    ingredient_id: int
    name: str
    function: Optional[str] = None
    description: Optional[str] = None
    evidence_summary: Optional[str] = None
    evidence_source: Optional[str] = None
    confidence_score: Optional[float] = None
    suitable_for: Optional[str] = None
    caution_for: Optional[str] = None
    is_fragrance: bool = False
    is_allergen: bool = False
    # Derived flags (simple heuristics, never definitive)
    is_concern: bool = False
    concern_reason: Optional[str] = None


class RiskAnalysis(BaseModel):
    product_id: int
    product_name: str
    brand: Optional[str] = None
    product_type: Optional[str] = None
    intended_use: Optional[str] = None
    ingredient_count: int
    unidentified_count: int = 0
    disclaimer: str = (
        "Ingredient presence alone cannot determine product safety. "
        "Concentration, formulation context, individual sensitivities, "
        "and exposure matter. This is not medical advice."
    )
    ingredients: list[IngredientRisk] = []


# ─── Scan ─────────────────────────────────────────────────────────────────────

class ScanIngredientRead(BaseModel):
    id: int
    raw_token: str
    normalized_token: Optional[str] = None
    candidate_ingredient_id: Optional[int] = None
    match_confidence: Optional[float] = None
    user_accepted: Optional[bool] = None
    ingredient: Optional[IngredientSummary] = None
    model_config = ConfigDict(from_attributes=True)


class ScanRead(BaseModel):
    id: int
    image_path: str
    ocr_raw_text: Optional[str] = None
    ocr_confidence: Optional[float] = None
    review_status: str
    product_id: Optional[int] = None
    scan_ingredients: list[ScanIngredientRead] = []
    model_config = ConfigDict(from_attributes=True)


class ScanListItem(BaseModel):
    id: int
    review_status: str
    ocr_confidence: Optional[float] = None
    product_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class ScanTextSubmit(BaseModel):
    text: str = Field(..., min_length=2, description="Raw ingredient text pasted by user")


class ScanIngredientPatch(BaseModel):
    """Used to accept/reject a single OCR token match."""
    user_accepted: bool


class MatlabIngredientScoreRequest(BaseModel):
    """Numeric component scores sent to the fixed MATLAB function."""
    values: list[float] = Field(..., min_length=1, max_length=100)


class MatlabIngredientScoreResponse(BaseModel):
    mean_score: float
    normalized_score: float
    risk_band: str
