"""
Package initializer for ORM models.
Imports all model classes so SQLAlchemy registers mappers.
"""

from .ingredient import Ingredient  # noqa: F401
from .product import Product, ProductIngredient  # noqa: F401
from .scan import Scan, ScanIngredient  # noqa: F401
