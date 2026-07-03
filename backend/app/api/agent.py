"""HTTP route for the Pricing Agent.

Thin router — orchestration lives in agents/pricing_agent.py, pricing math
in services/pricing.py. This file only validates input and maps exceptions.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.agents.pricing_agent import PricingAgent
from app.services.data_loader import DataLoader

router = APIRouter(tags=["agent"])

# Stateless — one instance is fine for the whole app.
_pricing_agent = PricingAgent()


def _loader(request: Request) -> DataLoader:
    return request.app.state.data


@router.post("/agent/pricing")
def agent_pricing(payload: dict, request: Request) -> dict:
    """Run the Pricing Agent workflow for the given property_id."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    property_id = payload.get("property_id")
    if not isinstance(property_id, str) or not property_id:
        raise HTTPException(
            status_code=400, detail="property_id is required (non-empty string)"
        )

    try:
        return _pricing_agent.recommend(property_id, _loader(request))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
