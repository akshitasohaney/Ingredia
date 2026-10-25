"""
Models package — imports all ORM classes so that Alembic's autogenerate
can discover every table in one import.
"""

from app.models.ingredient import Ingredient, IngredientAlias, IngredientConcern
from app.models.product import Product, ProductIngredient
from app.models.scan import Scan, ScanIngredient

__all__ = [
    "Ingredient",
    "IngredientAlias",
    "IngredientConcern",
    "Product",
    "ProductIngredient",
    "Scan",
    "ScanIngredient",
]
