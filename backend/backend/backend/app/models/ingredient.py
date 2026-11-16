"""
SQLAlchemy model for Ingredient.

Each row represents a canonical cosmetic ingredient with its INCI name,
function, evidence summary, and confidence score from the NLP pipeline.
"""

from typing import TYPE_CHECKING
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import ProductIngredient
    from app.models.scan import ScanIngredient


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    # INCI canonical name (may differ from display name)
    inci_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Comma-separated aliases / synonyms used for fuzzy matching
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    # High-level function e.g. "Emollient", "Preservative", "Humectant"
    function: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Free-text description of how it works / potential benefits
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Evidence-based safety / efficacy summary
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reference source (journal, CIR, EWG, etc.)
    evidence_source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 0-1 confidence that the evidence is adequate
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Skin types suited  (comma-separated: oily,dry,combination,normal,sensitive)
    suitable_for: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Skin types / conditions requiring caution (comma-separated)
    caution_for: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Fragrance / allergen flag
    is_fragrance: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    is_allergen: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(
        "ProductIngredient", back_populates="ingredient"
    )
    scan_ingredients: Mapped[list["ScanIngredient"]] = relationship(
        "ScanIngredient", back_populates="ingredient"
    )

    def __repr__(self) -> str:
        return f"<Ingredient id={self.id} name={self.name!r}>"
