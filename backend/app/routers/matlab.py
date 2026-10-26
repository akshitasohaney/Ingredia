"""Endpoints backed by vetted MATLAB functions."""
from fastapi import APIRouter, HTTPException

from app.schemas.schemas import MatlabIngredientScoreRequest, MatlabIngredientScoreResponse
from app.services.matlab_service import MatlabUnavailableError, matlab_service

router = APIRouter(prefix="/matlab", tags=["matlab"])


@router.post("/ingredient-score", response_model=MatlabIngredientScoreResponse)
def calculate_ingredient_score(payload: MatlabIngredientScoreRequest):
    """Calculate an aggregate score from zero-to-one input values in MATLAB."""
    try:
        return matlab_service.ingredient_score(payload.values)
    except MatlabUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
