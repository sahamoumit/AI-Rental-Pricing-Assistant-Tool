"""HTTP route for the analyst feedback service.

Thin router — persistence and business rules live in services/feedback.py.
This file validates the wire contract and maps service exceptions to
HTTP status codes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.data_loader import DataLoader
from app.services.feedback import record_feedback

router = APIRouter(tags=["feedback"])


def _loader(request: Request) -> DataLoader:
    return request.app.state.data


@router.post("/feedback")
def submit_feedback(payload: dict, request: Request) -> dict:
    """Record analyst feedback on a recommendation. Append-only, no learning."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    property_id = payload.get("property_id")
    if not isinstance(property_id, str) or not property_id:
        raise HTTPException(
            status_code=400, detail="property_id is required (non-empty string)"
        )

    recommended_rent = payload.get("recommended_rent")
    # bool is a subclass of int in Python — reject it explicitly.
    if isinstance(recommended_rent, bool) or not isinstance(recommended_rent, (int, float)):
        raise HTTPException(
            status_code=400, detail="recommended_rent is required (number)"
        )
    if recommended_rent <= 0:
        raise HTTPException(
            status_code=400, detail="recommended_rent must be positive"
        )

    ids = payload.get("selected_comparables")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(
            status_code=400,
            detail="selected_comparables is required (non-empty list)",
        )
    if any(not isinstance(cid, str) or not cid for cid in ids):
        raise HTTPException(
            status_code=400,
            detail="selected_comparables must contain non-empty strings",
        )

    feedback = payload.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise HTTPException(
            status_code=400, detail="feedback is required (non-empty string)"
        )

    try:
        return record_feedback(
            property_id,
            recommended_rent,
            ids,
            feedback,
            _loader(request),
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
