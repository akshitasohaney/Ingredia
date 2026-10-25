"""
ORM models for products and their ingredient associations.

Design notes:
- product_risk_score is NULL until explicitly computed (not 0 = "safe").
- risk_computed_at is set when the score is computed and cleared (set to NULL)
  whenever product_ingredients change, signalling a stale score.
- ProductIngredient.ingredient_id is nullable: an ingredient parsed from a label
  may not resolve to a known entry — this is "unresolved", not an error.
- match_method tracks provenance of how an ingredient was identified.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.scan import Scan


# ── Enum literals ─────────────────────────────────────────────────────────────

PRODUCT_CATEGORY_VALUES = (
    "skincare",
    "haircare",
    "makeup",
    "sunscreen",
    "fragrance",
    "bodycare",
    "other",
)

MATCH_METHOD_VALUES = ("exact", "alias", "fuzzy", "manual", "unresolved")


# ── Models ────────────────────────────────────────────────────────────────────


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # see PRODUCT_CATEGORY_VALUES
    barcode: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)

    # Computed risk score — NULL = not yet analyzed.
    # Never interpret NULL as "safe"; it means "unknown".
    product_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )

    # Relationships
    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(
        "ProductIngredient",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductIngredient.position",
    )
    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="product")

    # Store any additional CSV fields that do not map to a dedicated column
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, server_default="{}")

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r}>"



class ProductIngredient(Base):
    """
    Join table between Product and Ingredient.

    Each row represents one entry in a product's ingredient list.
    `position` follows label order (1 = first listed = highest concentration).
    `ingredient_id` is nullable — NULL means we couldn't resolve this token.
    """

    __tablename__ = "product_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: unresolved tokens have no matching ingredient record
    ingredient_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )

    # The raw text as it appeared on the label or in the OCR output
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Provenance of the match
    match_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # see MATCH_METHOD_VALUES
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product", back_populates="product_ingredients"
    )
    ingredient: Mapped["Ingredient | None"] = relationship(
        "Ingredient", back_populates="product_ingredients"
    )

    # Store any additional CSV fields that do not map to a dedicated column
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, server_default="{}")

    def __repr__(self) -> str:
        return (
            f"<ProductIngredient pos={self.position} "
            f"raw={self.raw_name!r} method={self.match_method}>"
        )
