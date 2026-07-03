"""HTTP route for the rent recommendation.

Thin router — the pricing math lives entirely in services/pricing.py. This
file just validates the input, pulls the target from the DataLoader, and
hands off.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.data_loader import DataLoader
from app.services.pricing import calculate_recommended_rent

router = APIRouter(tags=["pricing"])


def _loader(request: Request) -> DataLoader:
    return request.app.state.data


@router.post("/recommend")
def recommend(payload: dict, request: Request) -> dict:
    """Return a rent recommendation for the given property_id (auto-picked comps)."""
    property_id = payload.get("property_id") if isinstance(payload, dict) else None
    if not property_id:
        raise HTTPException(status_code=400, detail="property_id is required")

    try:
        return calculate_recommended_rent(property_id, _loader(request))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/recommend/recalculate")
def recalculate(payload: dict, request: Request) -> dict:
    """Recalculate the recommendation using only the analyst-selected comps."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    property_id = payload.get("property_id")
    if not isinstance(property_id, str) or not property_id:
        raise HTTPException(
            status_code=400, detail="property_id is required (non-empty string)"
        )

    ids = payload.get("selected_comparable_ids")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(
            status_code=400,
            detail="selected_comparable_ids is required (non-empty list)",
        )
    if any(not isinstance(cid, str) or not cid for cid in ids):
        raise HTTPException(
            status_code=400,
            detail="selected_comparable_ids must contain non-empty strings",
        )

    try:
        return calculate_recommended_rent(
            property_id, _loader(request), comparable_ids=ids
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
