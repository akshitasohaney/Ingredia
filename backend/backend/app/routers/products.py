"""
Products router — placeholder for Milestone 5.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products():
    """Placeholder — full implementation in Milestone 5."""
    return {"detail": "Product routes coming in Milestone 5."}
