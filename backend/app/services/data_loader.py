"""In-memory CSV data access for the AI Rental Pricing Assistant.

The prototype uses three CSVs (properties, rental history, analyst feedback).
They are small (~100/300/50 rows), so we read them once at startup and keep
them as pandas DataFrames. Every service/agent that follows should go through
this loader — it's the single source of truth for CSV access.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# CSVs currently live at backend/data/ (where generate_data.py writes them).
# Resolving relative to this file keeps the loader working regardless of the
# process's current working directory.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

PROPERTIES_CSV = DATA_DIR / "properties.csv"
RENTAL_HISTORY_CSV = DATA_DIR / "rental_history.csv"
ANALYST_FEEDBACK_CSV = DATA_DIR / "analyst_feedback.csv"


class DataLoader:
    """Loads the prototype's CSVs into memory and serves typed accessors."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.properties: pd.DataFrame = pd.DataFrame()
        self.rental_history: pd.DataFrame = pd.DataFrame()
        self.analyst_feedback: pd.DataFrame = pd.DataFrame()

    def load(self) -> None:
        """Read all CSVs into memory. Called once at app startup."""
        self.properties = pd.read_csv(self.data_dir / "properties.csv")
        self.rental_history = pd.read_csv(self.data_dir / "rental_history.csv")
        self.analyst_feedback = pd.read_csv(self.data_dir / "analyst_feedback.csv")

    # ---------- Property accessors ----------
    def list_properties(self) -> list[dict[str, Any]]:
        """Return every property as a plain dict list (JSON-serializable)."""
        return self.properties.to_dict(orient="records")

    def get_property(self, property_id: str) -> dict[str, Any] | None:
        """Return one property by id, or None if not found."""
        matches = self.properties[self.properties["property_id"] == property_id]
        if matches.empty:
            return None
        return matches.iloc[0].to_dict()
