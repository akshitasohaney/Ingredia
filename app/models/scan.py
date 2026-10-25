"""
SQLAlchemy models for Scan and ScanIngredient, representing an OCR scan of a product label
and the individual ingredient token matches.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.ingredient import Ingredient

# ---------------------------------------------------------------------------
# Scan model – stores the raw OCR result and overall review status.
# ---------------------------------------------------------------------------

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Review workflow status: pending_review, user_edited, user_confirmed, etc.
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending_review")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Optional link to a Product (once the scan is linked to a known product).
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    product: Mapped["Product | None"] = relationship("Product", back_populates="scans")

    # One‑to‑many relationship to ingredient matches derived from the OCR text.
    scan_ingredients: Mapped[list["ScanIngredient"]] = relationship(
        "ScanIngredient",
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Scan id={self.id} status={self.review_status!r}>"

# ---------------------------------------------------------------------------
# ScanIngredient model – stores each token extracted from the OCR text and the
# result of the matching pipeline.
# ---------------------------------------------------------------------------

class ScanIngredient(Base):
    __tablename__ = "scan_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("scans.id"), nullable=False)
    raw_token: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_ingredient_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ingredients.id"), nullable=True
    )
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Whether the user explicitly accepted this match (True/False) or hasn't decided (NULL).
    user_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Optional extra JSON payload for future extensions.
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, server_default="{}")

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="scan_ingredients")
    ingredient: Mapped["Ingredient | None"] = relationship("Ingredient")

    def __repr__(self) -> str:
        return (
            f"<ScanIngredient scan_id={self.scan_id} raw={self.raw_token!r} "
            f"ingredient_id={self.candidate_ingredient_id} confidence={self.match_confidence}>"
        )

