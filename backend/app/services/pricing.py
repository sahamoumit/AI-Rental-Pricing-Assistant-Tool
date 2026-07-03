"""Rental price recommendation service.

Deterministic, prototype-grade pricing. Given a target property, we:
  1. Fetch the top-N similar comparables (via services.similarity).
  2. Compute a similarity-weighted average rent as the base.
  3. Nudge it for area, amenities, and location deltas vs the weighted comps.
  4. Derive a confidence score from the comps' similarity spread.
  5. Widen a price band inversely to confidence.

No LLM here — the reasoning is in the numeric factors we return, which a
later Conversation Agent can narrate. Keep this file the single home for
the pricing math; the route just calls `recommend_rent()`.
"""
from __future__ import annotations

from typing import Any

from app.services.data_loader import DataLoader
from app.services.similarity import similarity, top_comparables

# --- Tunable constants (hand-picked for the Pune sample data). ---

# How many comparables feed the recommendation.
_TOP_N = 5

# Amenity flag columns evaluated for the amenity adjustment.
_AMENITY_FLAGS = ("parking", "balcony", "gym", "swimming_pool", "lift")

# ₹/month bump per amenity the target has that comps mostly lack (and
# penalty per amenity comps have that the target lacks). Small so this
# stays a nudge, not the story.
_AMENITY_BUMP = 400

# Comp-share threshold above which "most comps have it" is true.
_AMENITY_MAJORITY = 0.5

# ₹/month per unit delta vs weighted comp average.
# school_rating is on 0-10, walkability_score on 0-100 — smaller per-unit
# for the coarser scale so a full-scale swing lands in roughly the same range.
_SCHOOL_RATING_BUMP = 200
_WALKABILITY_BUMP = 20

# Confidence buckets from mean similarity of the top-N comps.
_CONFIDENCE_HIGH = 0.75
_CONFIDENCE_MED = 0.55

# Price band ± percentage of recommended rent, per confidence level.
_BAND_PCT = {"high": 0.05, "medium": 0.10, "low": 0.15}


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    total_w = sum(weights)
    if total_w == 0:
        return sum(values) / len(values) if values else 0.0
    return sum(v * w for v, w in zip(values, weights)) / total_w


def _confidence_level(score: float) -> str:
    if score >= _CONFIDENCE_HIGH:
        return "high"
    if score >= _CONFIDENCE_MED:
        return "medium"
    return "low"


def _round_to_100(value: float) -> int:
    return int(round(value / 100.0)) * 100


def _fmt_rupees(value: float) -> str:
    """Signed rupee formatting for notes: -300 → '-₹300', 800 → '+₹800', 0 → '₹0'."""
    rounded = _round_to_100(value)
    if rounded > 0:
        return f"+₹{rounded}"
    if rounded < 0:
        return f"-₹{abs(rounded)}"
    return "₹0"


def _comps_from_ids(
    target: dict[str, Any],
    comparable_ids: list[str],
    loader: DataLoader,
) -> list[dict[str, Any]]:
    """Build a comp list from an explicit id list (analyst recalculation).

    Validates the ids, dedupes preserving order, rejects the target itself,
    scores each survivor's similarity to the target, and returns the list
    sorted by similarity descending — same shape `top_comparables` returns.

    Raises LookupError if any id doesn't resolve.
    Raises ValueError if the list is empty or contains the target id.
    """
    if not comparable_ids:
        raise ValueError("selected_comparable_ids must be a non-empty list")

    seen: set[str] = set()
    ordered_unique: list[str] = []
    for cid in comparable_ids:
        if cid in seen:
            continue
        seen.add(cid)
        ordered_unique.append(cid)

    if target["property_id"] in seen:
        raise ValueError(
            f"Target {target['property_id']} cannot be its own comparable"
        )

    missing: list[str] = []
    resolved: list[dict[str, Any]] = []
    for cid in ordered_unique:
        cand = loader.get_property(cid)
        if cand is None:
            missing.append(cid)
        else:
            resolved.append(cand)
    if missing:
        raise LookupError(
            f"Comparable properties not found: {', '.join(missing)}"
        )

    scored: list[dict[str, Any]] = []
    for cand in resolved:
        row = dict(cand)
        row["similarity_score"] = round(similarity(target, cand), 3)
        scored.append(row)
    scored.sort(key=lambda r: r["similarity_score"], reverse=True)
    return scored


def calculate_recommended_rent(
    property_id: str,
    loader: DataLoader,
    comparable_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Produce a full rent recommendation for the property with `property_id`.

    Single public entry point for the pricing service. Later milestones (the
    Pricing Agent, the Orchestrator) should call this rather than
    reimplementing the math — everything below stays private.

    When `comparable_ids` is None (default), the top-N most similar properties
    are auto-picked. When provided (analyst recalculation), those exact
    properties are used as the comp set — the pricing math is otherwise
    identical.

    Raises LookupError if `property_id` or any supplied comparable id is not
    found. Raises ValueError if `comparable_ids` is provided but empty or
    contains the target's own id.
    """
    target = loader.get_property(property_id)
    if target is None:
        raise LookupError(f"Property {property_id} not found")

    all_properties = loader.list_properties()
    if comparable_ids is None:
        comps = top_comparables(target, all_properties, n=_TOP_N)
    else:
        comps = _comps_from_ids(target, comparable_ids, loader)
    if not comps:
        return {
            "property_id": target["property_id"],
            "recommended_rent": None,
            "confidence": {"score": 0.0, "level": "low"},
            "price_range": {"min": None, "max": None},
            "pricing_factors": {
                "base_rent": None,
                "area_adjustment": 0,
                "amenities_adjustment": 0,
                "location_adjustment": 0,
                "notes": ["No comparable properties available for this target."],
            },
            "comparables_used": [],
        }

    weights = [c["similarity_score"] for c in comps]
    rents = [float(c["current_rent"]) for c in comps]
    areas = [float(c["area_sqft"]) for c in comps]

    base_rent = _weighted_mean(rents, weights)
    weighted_area = _weighted_mean(areas, weights)

    # ---- Area adjustment: weighted per-sqft rate × delta.
    per_sqft = base_rent / weighted_area if weighted_area > 0 else 0.0
    target_area = float(target["area_sqft"])
    area_delta = target_area - weighted_area
    area_adjustment = per_sqft * area_delta

    # ---- Amenities: nudge for each flag where target differs from comp majority.
    amenities_adjustment = 0
    amenity_notes: list[str] = []
    for flag in _AMENITY_FLAGS:
        comp_share = _weighted_mean([float(c.get(flag, 0)) for c in comps], weights)
        target_has = int(target.get(flag, 0)) == 1
        if target_has and comp_share < _AMENITY_MAJORITY:
            amenities_adjustment += _AMENITY_BUMP
            amenity_notes.append(f"+₹{_AMENITY_BUMP} — target has {flag}, most comps do not")
        elif not target_has and comp_share > _AMENITY_MAJORITY:
            amenities_adjustment -= _AMENITY_BUMP
            amenity_notes.append(f"-₹{_AMENITY_BUMP} — target lacks {flag}, most comps have it")

    # ---- Location: school_rating + walkability_score deltas vs weighted comps.
    weighted_school = _weighted_mean(
        [float(c.get("school_rating", 0) or 0) for c in comps], weights
    )
    weighted_walk = _weighted_mean(
        [float(c.get("walkability_score", 0) or 0) for c in comps], weights
    )
    target_school = float(target.get("school_rating", 0) or 0)
    target_walk = float(target.get("walkability_score", 0) or 0)
    school_adj = (target_school - weighted_school) * _SCHOOL_RATING_BUMP
    walk_adj = (target_walk - weighted_walk) * _WALKABILITY_BUMP
    location_adjustment = school_adj + walk_adj

    # ---- Confidence from mean similarity of the comps.
    conf_score = sum(weights) / len(weights)
    conf_level = _confidence_level(conf_score)

    recommended_raw = base_rent + area_adjustment + amenities_adjustment + location_adjustment
    recommended_rent = _round_to_100(recommended_raw)

    band_pct = _BAND_PCT[conf_level]
    price_min = _round_to_100(recommended_rent * (1 - band_pct))
    price_max = _round_to_100(recommended_rent * (1 + band_pct))

    # ---- Human-readable factor notes for the UI/analyst.
    notes = [
        f"Base ₹{_round_to_100(base_rent)} = similarity-weighted mean of {len(comps)} comps",
    ]
    if abs(area_delta) >= 20:
        direction = "larger" if area_delta > 0 else "smaller"
        notes.append(
            f"Area adj {_fmt_rupees(area_adjustment)} — "
            f"target is {abs(int(area_delta))} sqft {direction} than comp avg"
        )
    notes.extend(amenity_notes)
    if abs(school_adj) >= 100:
        notes.append(
            f"School adj {_fmt_rupees(school_adj)} — "
            f"rating {target_school:.1f} vs comp avg {weighted_school:.1f}"
        )
    if abs(walk_adj) >= 100:
        notes.append(
            f"Walkability adj {_fmt_rupees(walk_adj)} — "
            f"score {target_walk:.0f} vs comp avg {weighted_walk:.0f}"
        )

    return {
        "property_id": target["property_id"],
        "recommended_rent": recommended_rent,
        "confidence": {"score": round(conf_score, 3), "level": conf_level},
        "price_range": {"min": price_min, "max": price_max},
        "pricing_factors": {
            "base_rent": _round_to_100(base_rent),
            "area_adjustment": _round_to_100(area_adjustment),
            "amenities_adjustment": int(amenities_adjustment),
            "location_adjustment": _round_to_100(location_adjustment),
            "notes": notes,
        },
        "comparables_used": [
            {
                "property_id": c["property_id"],
                "address": c.get("address"),
                "locality": c.get("locality"),
                "current_rent": int(c["current_rent"]),
                "similarity_score": c["similarity_score"],
            }
            for c in comps
        ],
    }
