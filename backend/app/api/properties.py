"""HTTP routes for browsing properties.

Thin router — no business logic here. Delegates to the DataLoader stored on
app.state during startup. Adding real logic here is a smell; put it in a
service or agent module instead.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.data_loader import DataLoader
from app.services.similarity import top_comparables

router = APIRouter(prefix="/properties", tags=["properties"])


def _loader(request: Request) -> DataLoader:
    """Grab the singleton DataLoader that main.py attached at startup."""
    return request.app.state.data


@router.get("")
def list_properties(request: Request) -> list[dict]:
    """Return every property. Used to populate the frontend dropdown."""
    return _loader(request).list_properties()


@router.get("/{property_id}")
def get_property(property_id: str, request: Request) -> dict:
    """Return full details for a single property, or 404 if unknown."""
    prop = _loader(request).get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail=f"Property {property_id} not found")
    return prop


@router.get("/{property_id}/comparables")
def get_comparables(property_id: str, request: Request) -> list[dict]:
    """Return the top 5 comparable properties for the given target, or 404 if unknown."""
    loader = _loader(request)
    target = loader.get_property(property_id)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Property {property_id} not found")
    return top_comparables(target, loader.list_properties(), n=5)
