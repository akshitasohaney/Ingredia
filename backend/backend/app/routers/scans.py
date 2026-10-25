"""
Scans router — placeholder for Milestone 4.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("")
def list_scans():
    """Placeholder — full implementation in Milestone 4."""
    return {"detail": "Scan routes coming in Milestone 4."}
