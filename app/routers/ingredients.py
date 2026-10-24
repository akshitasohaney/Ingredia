"""
Ingredients router — placeholder for Milestone 2.
A minimal health-check route is included so the app starts without errors.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("")
def list_ingredients():
    """Placeholder — full implementation in Milestone 2."""
    return {"detail": "Ingredient routes coming in Milestone 2."}
