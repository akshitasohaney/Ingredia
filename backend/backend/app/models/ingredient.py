"""
ORM models for the ingredient knowledge base.

Design notes:
- hazard_score is NULL when evidence is insufficient, never defaulted to 0.
- data_completeness is mandatory; it is the honest answer when we lack data.
- Every concern row requires source_name (non-nullable); source_url is optional
  because some sources are books or regulatory documents without stable URLs.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import ProductIngredient


# ── Enum literals (enforced at application layer via Pydantic, not DB) ────────

HAZARD_BASIS_VALUES = (
    "animal_study",
    "in_vitro",
    "epidemiological",
    "regulatory_ban",
    "insufficient_data",
)

DATA_COMPLETENESS_VALUES = ("complete", "partial", "minimal", "none")

EU_ANNEX_STATUS_VALUES = ("permitted", "restricted", "prohibited", "not_regulated")

ALIAS_TYPE_VALUES = ("inci", "common", "brand", "abbreviation")

CONCERN_TYPE_VALUES = (
    "carcinogen",
    "endocrine_disruptor",
    "allergen",
    "irritant",
    "neurotoxin",
    "environmental",
    "reproductive_toxin",
)

SEVERITY_VALUES = ("confirmed", "suspected", "possible", "disputed")


# ── Models ────────────────────────────────────────────────────────────────────


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Regulatory identifiers — nullable because not every ingredient is catalogued
    cas_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ec_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Stored as JSON string: e.g. '["emollient", "preservative"]'
    function_tags: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NULL means "we don't have enough data to score this"
    hazard_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hazard_basis: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # see HAZARD_BASIS_VALUES

    # Mandatory: tells UI and API consumers how much to trust the score
    data_completeness: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )

    # External reference scores — NULL = not listed in that registry
    ewg_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eu_annex_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    aliases: Mapped[list["IngredientAlias"]] = relationship(
        "IngredientAlias", back_populates="ingredient", cascade="all, delete-orphan"
    )
    concerns: Mapped[list["IngredientConcern"]] = relationship(
        "IngredientConcern", back_populates="ingredient", cascade="all, delete-orphan"
    )
    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(
        "ProductIngredient", back_populates="ingredient"
    )

    def __repr__(self) -> str:
        return f"<Ingredient id={self.id} name={self.canonical_name!r}>"


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # see ALIAS_TYPE_VALUES

    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient", back_populates="aliases"
    )

    def __repr__(self) -> str:
        return f"<IngredientAlias {self.alias!r} ({self.alias_type})>"


class IngredientConcern(Base):
    __tablename__ = "ingredient_concerns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )

    # What kind of concern this is
    concern_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # see CONCERN_TYPE_VALUES
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # see SEVERITY_VALUES

    # Human-readable summary — capped at 500 chars by Pydantic validator
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Source fields — source_name is mandatory; source_url is optional
    # (books, regulatory PDFs may not have stable URLs)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Qualifies the concern: e.g. "occupational exposure only", "at >2% concentration"
    population_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(
        "Ingredient", back_populates="concerns"
    )

    def __repr__(self) -> str:
        return (
            f"<IngredientConcern {self.concern_type}/{self.severity} "
            f"ingredient_id={self.ingredient_id}>"
        )
