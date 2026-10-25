"""
Pydantic schemas for the Ingredient domain.

Naming convention:
  *Create  — request body for POST (fields required to create)
  *Update  — request body for PATCH (all fields optional)
  *Read    — response body (includes server-set fields like id, created_at)
  *Detail  — extended response including nested relationships
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.ingredient import (
    ALIAS_TYPE_VALUES,
    CONCERN_TYPE_VALUES,
    DATA_COMPLETENESS_VALUES,
    EU_ANNEX_STATUS_VALUES,
    HAZARD_BASIS_VALUES,
    SEVERITY_VALUES,
)

# ── Literal types derived from the model constants ────────────────────────────

AliasType = Literal["inci", "common", "brand", "abbreviation"]
ConcernType = Literal[
    "carcinogen",
    "endocrine_disruptor",
    "allergen",
    "irritant",
    "neurotoxin",
    "environmental",
    "reproductive_toxin",
]
Severity = Literal["confirmed", "suspected", "possible", "disputed"]
HazardBasis = Literal[
    "animal_study", "in_vitro", "epidemiological", "regulatory_ban", "insufficient_data"
]
DataCompleteness = Literal["complete", "partial", "minimal", "none"]
EuAnnexStatus = Literal["permitted", "restricted", "prohibited", "not_regulated"]


# ── Alias schemas ─────────────────────────────────────────────────────────────


class IngredientAliasCreate(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)
    alias_type: AliasType


class IngredientAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alias: str
    alias_type: AliasType


# ── Concern schemas ───────────────────────────────────────────────────────────


class IngredientConcernCreate(BaseModel):
    concern_type: ConcernType
    severity: Severity
    summary: Annotated[str, Field(min_length=10, max_length=500)]
    # source_name is NOT optional — it is the anti-invention guardrail.
    # Every concern MUST cite where the evidence comes from.
    source_name: Annotated[str, Field(min_length=3, max_length=255)]
    source_url: str | None = Field(
        default=None,
        description="Direct URL to the source document. Optional because some sources "
                    "(books, regulatory PDFs) lack stable URLs.",
    )
    population_context: str | None = Field(
        default=None,
        max_length=500,
        description="Qualifies who the concern applies to (e.g. 'occupational exposure only').",
    )

    @field_validator("source_url", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Treat empty string as None so CSV rows with empty source_url work."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class IngredientConcernRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    concern_type: ConcernType
    severity: Severity
    summary: str
    source_name: str
    source_url: str | None
    population_context: str | None


# ── Ingredient schemas ────────────────────────────────────────────────────────


class IngredientCreate(BaseModel):
    canonical_name: str = Field(..., min_length=2, max_length=255)
    cas_number: str | None = Field(default=None, max_length=50)
    ec_number: str | None = Field(default=None, max_length=50)
    # function_tags is stored as a JSON string in the DB; accept a list here.
    function_tags: list[str] | None = None
    hazard_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="0–10 hazard score. NULL means insufficient data, NOT safe.",
    )
    hazard_basis: HazardBasis | None = None
    data_completeness: DataCompleteness = "none"
    ewg_score: int | None = Field(default=None, ge=1, le=10)
    eu_annex_status: EuAnnexStatus | None = None

    @model_validator(mode="after")
    def hazard_score_requires_basis(self) -> "IngredientCreate":
        """If a hazard_score is provided, hazard_basis must also be provided."""
        if self.hazard_score is not None and self.hazard_basis is None:
            raise ValueError("hazard_basis is required when hazard_score is provided.")
        return self


class IngredientUpdate(BaseModel):
    """All fields optional — supports true PATCH semantics."""

    canonical_name: str | None = Field(default=None, min_length=2, max_length=255)
    cas_number: str | None = None
    ec_number: str | None = None
    function_tags: list[str] | None = None
    hazard_score: float | None = Field(default=None, ge=0.0, le=10.0)
    hazard_basis: HazardBasis | None = None
    data_completeness: DataCompleteness | None = None
    ewg_score: int | None = Field(default=None, ge=1, le=10)
    eu_annex_status: EuAnnexStatus | None = None


class IngredientRead(BaseModel):
    """Flat read schema — used in list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    cas_number: str | None
    ec_number: str | None
    function_tags: list[str] | None
    hazard_score: float | None
    hazard_basis: HazardBasis | None
    data_completeness: DataCompleteness
    ewg_score: int | None
    eu_annex_status: EuAnnexStatus | None
    created_at: datetime
    updated_at: datetime

    @field_validator("function_tags", mode="before")
    @classmethod
    def parse_function_tags(cls, v):
        """
        The DB stores function_tags as a JSON string; deserialise it.
        Returns None if the value is None or an empty string.
        """
        if v is None or v == "":
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except (json.JSONDecodeError, ValueError):
                return None
        return None


class IngredientDetail(IngredientRead):
    """Full read schema — includes nested concerns and aliases."""

    concerns: list[IngredientConcernRead] = []
    aliases: list[IngredientAliasRead] = []

    # The concern_summary provides a quick human-readable signal for the UI.
    concern_summary: str | None = None

    @model_validator(mode="after")
    def build_concern_summary(self) -> "IngredientDetail":
        """
        Build a one-line textual summary of the most severe concern,
        e.g. 'Confirmed carcinogen (IARC Monograph Volume 100F)'.
        """
        if not self.concerns:
            self.concern_summary = None
            return self

        severity_rank = {"confirmed": 0, "suspected": 1, "possible": 2, "disputed": 3}
        top = min(self.concerns, key=lambda c: severity_rank.get(c.severity, 99))
        self.concern_summary = (
            f"{top.severity.capitalize()} {top.concern_type.replace('_', ' ')} "
            f"({top.source_name})"
        )
        return self


# ── Paginated list response ───────────────────────────────────────────────────


class PaginatedIngredients(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[IngredientRead]
