"""
SQLAlchemy models for Product and ProductIngredient (association).

Product: the skincare product (name, brand, product type, intended use).
ProductIngredient: ordered list of ingredients for a product, with position.
"""

from typing import TYPE_CHECKING
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.scan import Scan


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    product_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    intended_use: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(
        "ProductIngredient",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductIngredient.position",
    )
    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} brand={self.brand!r}>"


class ProductIngredient(Base):
    """Association table between Product and Ingredient.
    Stores ingredient order (position), which is for display ONLY —
    it must NOT be used to infer concentration.
    """
    __tablename__ = "product_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingredients.id"), nullable=False
    )
    # Order in the ingredient list (1-indexed). Display only.
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Raw text as it appeared on the label
    raw_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="product_ingredients")
    ingredient: Mapped["Ingredient"] = relationship("Ingredient", back_populates="product_ingredients")
