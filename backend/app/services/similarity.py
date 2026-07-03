"""Similarity scoring for comparable property retrieval.

Pure functions — no state, no CSV I/O. Callers hand us the target property
and the candidate list; we return the top-N candidates ranked by a
transparent weighted similarity score.

Prototype-grade: hand-tuned weights, deterministic. A later Comparable Agent
milestone can wrap this without touching the scoring code.
"""
from __future__ import annotations

import math
from typing import Any

# Binary 0/1 flag columns in properties.csv.
_AMENITY_FLAGS = ("parking", "balcony", "gym", "swimming_pool", "lift")

# Sub-score weights. Sum to 1.0 so the final similarity stays in [0, 1].
# If you change these, document why in the commit message — this is the
# whole "why is P0042 comparable" story.
_WEIGHTS = {
    "locality":  0.25,
    "bedrooms":  0.20,
    "area":      0.20,
    "type":      0.15,
    "bathrooms": 0.10,
    "amenities": 0.10,
}

# Beyond this distance a cross-locality candidate scores zero on location.
_LOCALITY_FALLOFF_KM = 5.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _locality_score(t: dict, c: dict) -> float:
    if t.get("locality") and t["locality"] == c.get("locality"):
        return 1.0
    d_km = _haversine_km(t["latitude"], t["longitude"], c["latitude"], c["longitude"])
    return max(0.0, 1.0 - d_km / _LOCALITY_FALLOFF_KM)


def _step_score(delta: int) -> float:
    if delta == 0:
        return 1.0
    if delta == 1:
        return 0.5
    return 0.0


def _bedroom_score(t: dict, c: dict) -> float:
    return _step_score(abs(int(t["bedrooms"]) - int(c["bedrooms"])))


def _bathroom_score(t: dict, c: dict) -> float:
    return _step_score(abs(int(t["bathrooms"]) - int(c["bathrooms"])))


def _area_score(t: dict, c: dict) -> float:
    ta = float(t["area_sqft"])
    if ta <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(float(c["area_sqft"]) - ta) / ta)


def _type_score(t: dict, c: dict) -> float:
    return 1.0 if t.get("property_type") == c.get("property_type") else 0.0


def _amenities_score(t: dict, c: dict) -> float:
    matches = sum(1 for f in _AMENITY_FLAGS if int(t.get(f, 0)) == int(c.get(f, 0)))
    return matches / len(_AMENITY_FLAGS)


def similarity(target: dict[str, Any], candidate: dict[str, Any]) -> float:
    """Weighted similarity in [0, 1]. Higher = more comparable."""
    return (
        _WEIGHTS["locality"]  * _locality_score(target, candidate)
        + _WEIGHTS["bedrooms"]  * _bedroom_score(target, candidate)
        + _WEIGHTS["area"]      * _area_score(target, candidate)
        + _WEIGHTS["type"]      * _type_score(target, candidate)
        + _WEIGHTS["bathrooms"] * _bathroom_score(target, candidate)
        + _WEIGHTS["amenities"] * _amenities_score(target, candidate)
    )


def top_comparables(
    target: dict[str, Any],
    all_properties: list[dict[str, Any]],
    n: int = 5,
) -> list[dict[str, Any]]:
    """Return the top-N candidates by similarity, excluding the target itself.

    Each returned dict is a shallow copy of the candidate augmented with a
    'similarity_score' field (rounded to 3 decimals).
    """
    scored: list[tuple[float, dict[str, Any]]] = []
    for cand in all_properties:
        if cand["property_id"] == target["property_id"]:
            continue
        scored.append((similarity(target, cand), cand))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    top: list[dict[str, Any]] = []
    for score, cand in scored[:n]:
        row = dict(cand)
        row["similarity_score"] = round(score, 3)
        top.append(row)
    return top
