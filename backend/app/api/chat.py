"""HTTP route for the AI conversation service.

Thin router — LLM logic lives in services/chat.py. This file validates
the request body and maps service errors to HTTP status codes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.services.chat import answer_question
from app.services.data_loader import DataLoader

router = APIRouter(tags=["chat"])


def _loader(request: Request) -> DataLoader:
    return request.app.state.data


@router.post("/chat")
def chat(payload: dict, request: Request) -> dict:
    """Answer an analyst question grounded in an existing recommendation."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    property_id = payload.get("property_id")
    if not isinstance(property_id, str) or not property_id:
        raise HTTPException(
            status_code=400, detail="property_id is required (non-empty string)"
        )

    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(
            status_code=400, detail="question is required (non-empty string)"
        )

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, dict) or not recommendation:
        raise HTTPException(
            status_code=400,
            detail=(
                "recommendation is required — call /recommend first and pass its "
                "response here so chat can reuse it without recomputing"
            ),
        )

    try:
        return answer_question(
            property_id, question, recommendation, _loader(request)
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        # LLM (Ollama) unreachable, model missing, or upstream failure — all 503.
        # The detail carries the exact remediation command where applicable.
        raise HTTPException(status_code=503, detail=str(e)) from e
