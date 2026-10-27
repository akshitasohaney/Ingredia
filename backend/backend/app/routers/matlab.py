"""Ingredient-scoring endpoints retained at the legacy MATLAB API path."""
from fastapi import APIRouter

from app.schemas.schemas import MatlabIngredientScoreRequest, MatlabIngredientScoreResponse
from app.services.ingredient_scoring import ingredient_score

router = APIRouter(prefix="/matlab", tags=["matlab"])


@router.post("/ingredient-score", response_model=MatlabIngredientScoreResponse)
def calculate_ingredient_score(payload: MatlabIngredientScoreRequest):
    """Calculate the former MATLAB score locally in Python."""
    return ingredient_score(payload.values)
