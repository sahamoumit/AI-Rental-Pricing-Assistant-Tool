"""LLM-backed conversation service for the AI Rental Pricing Assistant.

Given a property_id, a natural-language question, and the recommendation
the frontend already fetched, this service assembles a grounded prompt,
calls a local Llama model via Ollama's HTTP API, and returns the answer
plus the comparables it was grounded in.

Design notes:
- We do NOT recompute the recommendation here. The caller (frontend)
  passes back the object it received from `/recommend` (or
  `/recommend/recalculate`). That keeps chat cheap and preserves the
  analyst's possibly-recalculated comp set as the source of truth.
- Target property details are pulled fresh from the DataLoader — cheap
  (in-memory CSV) and lets the LLM see fields the recommendation payload
  intentionally omits (amenities, school_rating, walkability_score, ...).
- Prompt template lives in `app/prompts/chat_prompt.txt` so it can be
  iterated without touching Python.
- LLM runs locally via Ollama. We hit its HTTP API directly with httpx
  rather than pulling in the `ollama` Python SDK — one short POST, no
  extra dependency.
- `OLLAMA_BASE_URL` / `OLLAMA_MODEL` are read from the environment
  (`python-dotenv` loads `backend/.env` at import time). No API key —
  Ollama runs locally, unauthenticated.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.services.data_loader import DataLoader

load_dotenv()

_DEFAULT_MODEL = "llama3.2"
_DEFAULT_BASE_URL = "http://localhost:11434"

# Local Llama on CPU can take a while for the first token, and the route
# is synchronous. Generous ceiling — tune if it bites.
_OLLAMA_TIMEOUT_S = 120.0

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "chat_prompt.txt"

_SYSTEM_MARKER = "[SYSTEM]"
_USER_MARKER = "[USER]"

# Target-property fields worth surfacing to the LLM. We deliberately drop
# columns the model can't reason usefully about (lat/long, floor numbers,
# maintenance fee, occupancy).
_TARGET_FIELDS = (
    "property_id", "address", "locality", "property_type",
    "bedrooms", "bathrooms", "area_sqft", "furnishing", "property_age",
    "parking", "balcony", "gym", "swimming_pool", "lift",
    "school_rating", "walkability_score", "crime_index",
)


def _load_prompt_template() -> tuple[str, str]:
    """Return (system_prompt, user_template) parsed from the prompt file."""
    text = _PROMPT_PATH.read_text(encoding="utf-8")
    if _SYSTEM_MARKER not in text or _USER_MARKER not in text:
        raise RuntimeError(
            f"Chat prompt template missing {_SYSTEM_MARKER} or {_USER_MARKER} marker"
        )
    _, rest = text.split(_SYSTEM_MARKER, 1)
    system_part, user_part = rest.split(_USER_MARKER, 1)
    return system_part.strip(), user_part.strip()


# Load once at import — the template is small and static.
_SYSTEM_PROMPT, _USER_TEMPLATE = _load_prompt_template()


def _target_summary(target: dict[str, Any]) -> dict[str, Any]:
    return {k: target[k] for k in _TARGET_FIELDS if k in target}


def _references(recommendation: dict[str, Any]) -> list[dict[str, Any]]:
    """Traceable comp list returned to the caller as `references`."""
    comps = recommendation.get("comparables_used") or []
    return [
        {
            "property_id": c.get("property_id"),
            "address": c.get("address"),
            "locality": c.get("locality"),
            "current_rent": c.get("current_rent"),
        }
        for c in comps
    ]


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    """POST to Ollama's /api/chat and return the assistant text.

    Raises RuntimeError with an operator-facing message for any failure
    mode the route should surface as HTTP 503.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
    url = f"{base_url}/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }

    try:
        response = httpx.post(url, json=body, timeout=_OLLAMA_TIMEOUT_S)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise RuntimeError(
            f"Ollama not reachable at {base_url} — is `ollama serve` running? ({e})"
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"Ollama request failed: {e}") from e

    if response.status_code == 404:
        # Ollama's shape: {"error": "model 'x' not found, try pulling it first"}
        raise RuntimeError(
            f"Model '{model}' not found in Ollama — run `ollama pull {model}`"
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama request failed (HTTP {response.status_code}): {response.text}"
        )

    try:
        payload = response.json()
    except ValueError as e:
        raise RuntimeError(f"Ollama returned non-JSON response: {response.text}") from e

    message = payload.get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError(f"Ollama returned an empty message: {payload}")
    return content


def answer_question(
    property_id: str,
    question: str,
    recommendation: dict[str, Any],
    loader: DataLoader,
) -> dict[str, Any]:
    """Answer an analyst question grounded in an existing recommendation.

    Raises:
        LookupError: `property_id` is not in the sample data.
        RuntimeError: Ollama is unreachable, the model is missing, or the
            LLM call failed. Route maps this to HTTP 503.
    """
    target = loader.get_property(property_id)
    if target is None:
        raise LookupError(f"Property {property_id} not found")

    user_prompt = (
        _USER_TEMPLATE
        .replace("{{property}}", json.dumps(_target_summary(target), indent=2, default=str))
        .replace("{{recommendation}}", json.dumps(recommendation, indent=2, default=str))
        .replace("{{question}}", question.strip())
    )

    answer = _call_ollama(_SYSTEM_PROMPT, user_prompt)
    return {
        "answer": answer,
        "references": _references(recommendation),
    }
