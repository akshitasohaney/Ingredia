"""
ORM models for OCR scans and their provisional ingredient tokens.

Design notes:
- review_status enforces the OCR review gate described in the architecture plan.
  Analysis is only permitted after a scan reaches 'user_confirmed' or 'user_edited'.
- scan_ingredients is a STAGING table: tokens here are provisional candidates,
  not confirmed product ingredients.
- user_accepted is three-valued: NULL = not reviewed, True = accepted, False = rejected.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.product import Product


# ── Enum literals ─────────────────────────────────────────────────────────────

REVIEW_STATUS_VALUES = (
    "pending_review",   # OCR done; awaiting user review
    "user_confirmed",   # User approved the raw OCR text as-is
    "user_edited",      # User made corrections before confirming
    "rejected",         # User discarded this scan entirely
)


# ── Models ────────────────────────────────────────────────────────────────────


class Scan(Base):
    """
    Represents one uploaded image and its OCR lifecycle.

    The product_id is intentionally nullable at creation time: the scan is an
    independent entity until the user links it to a product after reviewing the
    OCR output.
    """

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Linked after user confirms the scan, not at upload time
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Relative path under uploads/; the actual file is on disk, not in the DB
    image_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Raw Tesseract output — NULL if OCR failed entirely
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Mean word-level Tesseract confidence (0–100); NULL if OCR failed
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Gate: analysis is blocked until this reaches 'user_confirmed' or 'user_edited'
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_review"
    )

    # User-edited version; populated by PATCH /scans/{id}/confirm
    confirmed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Human-readable error if OCR pipeline raised an exception
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    # Relationships
    product: Mapped["Product | None"] = relationship("Product", back_populates="scans")
    scan_ingredients: Mapped[list["ScanIngredient"]] = relationship(
        "ScanIngredient",
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Scan id={self.id} status={self.review_status} "
            f"confidence={self.ocr_confidence}>"
        )


class ScanIngredient(Base):
    """
    Provisional NLP-parsed ingredient token from a confirmed scan.

    This is a staging table. Rows here are candidates; they must be reviewed
    by the user before being promoted to product_ingredients.

    Three-valued user_accepted:
      NULL  → not yet reviewed by user
      True  → user accepted this match
      False → user rejected this match
    """

    __tablename__ = "scan_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )

    # Token as extracted from the OCR / NLP tokenizer
    raw_token: Mapped[str] = mapped_column(Text, nullable=False)
    # Token after normalization (lowercased, stripped)
    normalized_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Best-match suggestion from NLP pipeline; NULL if no match found
    candidate_ingredient_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Three-valued: NULL = not reviewed, True = accepted, False = rejected
    user_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="scan_ingredients")
    candidate_ingredient: Mapped["Ingredient | None"] = relationship("Ingredient")

    def __repr__(self) -> str:
        return (
            f"<ScanIngredient raw={self.raw_token!r} "
            f"confidence={self.match_confidence} accepted={self.user_accepted}>"
        )
