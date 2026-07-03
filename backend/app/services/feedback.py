"""Analyst feedback capture service.

Persists analyst feedback on rent recommendations to an append-only CSV.
No learning loop yet — a future Learning Agent will read this file and
turn it into training signal. This module only writes.

Design notes:
- One row per feedback submission. Columns: timestamp (ISO 8601 UTC),
  property_id, recommended_rent, selected_comparables (JSON-encoded list),
  feedback (analyst text). `csv.writer` handles quoting so multi-line
  feedback and the JSON blob survive intact.
- File path resolves to `backend/data/analyst_feedback.csv` via the
  DataLoader constants — single source of truth for CSV locations.
- Header is written lazily: only when the file is missing or empty.
  Every subsequent submission appends one row.
- No file locking. Fine at prototype altitude (single analyst); revisit
  when the tool becomes multi-user.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.data_loader import ANALYST_FEEDBACK_CSV, DataLoader

FEEDBACK_CSV: Path = ANALYST_FEEDBACK_CSV

_HEADER = (
    "timestamp",
    "property_id",
    "recommended_rent",
    "selected_comparables",
    "feedback",
)


def _ensure_header(path: Path) -> None:
    """Write the CSV header row if the file is missing or empty."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(_HEADER)


def _dedupe_preserving_order(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def record_feedback(
    property_id: str,
    recommended_rent: float,
    selected_comparables: list[str],
    feedback: str,
    loader: DataLoader,
) -> dict[str, Any]:
    """Validate against the property catalog and append one row of feedback.

    Assumes the caller has already validated types/emptiness (route does
    that). Here we enforce business rules: ids exist, target is not its
    own comparable.

    Raises:
        LookupError: `property_id` or any comp id is unknown.
        ValueError: target listed as its own comparable.
        RuntimeError: CSV write failed (route maps to HTTP 500).
    """
    if loader.get_property(property_id) is None:
        raise LookupError(f"Property {property_id} not found")

    unique_ids = _dedupe_preserving_order(selected_comparables)

    if property_id in unique_ids:
        raise ValueError(
            f"Target {property_id} cannot be listed as its own comparable"
        )

    missing = [cid for cid in unique_ids if loader.get_property(cid) is None]
    if missing:
        raise LookupError(
            f"Comparable properties not found: {', '.join(missing)}"
        )

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "property_id": property_id,
        "recommended_rent": recommended_rent,
        "selected_comparables": json.dumps(unique_ids),
        "feedback": feedback.strip(),
    }

    try:
        _ensure_header(FEEDBACK_CSV)
        with open(FEEDBACK_CSV, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_HEADER).writerow(row)
    except OSError as e:
        raise RuntimeError(f"Failed to write feedback file: {e}") from e

    return {
        "success": True,
        "message": f"Feedback recorded for {property_id}",
    }
