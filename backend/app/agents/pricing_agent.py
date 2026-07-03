"""Pricing Agent — orchestration layer over the Comparable + Pricing services.

The agent does not do any pricing math. It:
  1. Loads the target property.
  2. Asks the Comparable Service for the top-N similar properties.
  3. Evaluates comp quality (count + mean similarity).
  4. If confidence looks low, retries once with a broader search (larger N)
     and hands the widened comp set to the pricing service explicitly.
  5. Delegates the final rent calculation to services.pricing — the single
     home of the pricing formula.
  6. Returns the pricing service's payload augmented with a high-level
     `agent_reasoning` trace so the analyst can see what the agent did.

Stateless by design: the class holds only tunables. All per-call data
(target, comps, loader) is passed through method arguments.
"""
from __future__ import annotations

from typing import Any

from app.services.data_loader import DataLoader
from app.services.pricing import calculate_recommended_rent
from app.services.similarity import top_comparables

# Mirrors services.pricing._CONFIDENCE_MED — below this mean similarity we
# consider the comp set weak enough to justify a broader retry.
_DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.55
_DEFAULT_TOP_N = 5
_DEFAULT_BROADER_TOP_N = 10


class PricingAgent:
    def __init__(
        self,
        low_confidence_threshold: float = _DEFAULT_LOW_CONFIDENCE_THRESHOLD,
        default_top_n: int = _DEFAULT_TOP_N,
        broader_top_n: int = _DEFAULT_BROADER_TOP_N,
    ) -> None:
        self.low_confidence_threshold = low_confidence_threshold
        self.default_top_n = default_top_n
        self.broader_top_n = broader_top_n

    def recommend(self, property_id: str, loader: DataLoader) -> dict[str, Any]:
        """Orchestrate a rent recommendation for `property_id`.

        Raises LookupError if the property is unknown (route maps to 404).
        """
        reasoning: list[str] = []

        target = loader.get_property(property_id)
        if target is None:
            raise LookupError(f"Property {property_id} not found")
        reasoning.append(f"Loaded target property {property_id}.")

        all_properties = loader.list_properties()
        comps = top_comparables(target, all_properties, n=self.default_top_n)
        mean_sim = _mean_similarity(comps)
        reasoning.append(
            f"Fetched {len(comps)} comparables via Comparable Service "
            f"(n={self.default_top_n}); mean similarity {mean_sim:.2f}."
        )

        comparable_ids: list[str] | None = None
        if mean_sim < self.low_confidence_threshold and comps:
            broader = top_comparables(
                target, all_properties, n=self.broader_top_n
            )
            broader_mean = _mean_similarity(broader)
            reasoning.append(
                f"Mean similarity below threshold "
                f"{self.low_confidence_threshold:.2f} — retried with "
                f"n={self.broader_top_n}; got {len(broader)} comps, "
                f"mean similarity {broader_mean:.2f}."
            )
            comparable_ids = [c["property_id"] for c in broader]
        else:
            reasoning.append("Confidence acceptable — no retry needed.")

        recommendation = calculate_recommended_rent(
            property_id, loader, comparable_ids=comparable_ids
        )
        reasoning.append(
            "Delegated final rent calculation to services.pricing "
            f"(confidence: {recommendation['confidence']['level']})."
        )

        return {
            "recommended_rent": recommendation["recommended_rent"],
            "confidence": recommendation["confidence"],
            "price_range": recommendation["price_range"],
            "pricing_factors": recommendation["pricing_factors"],
            "comparables_used": recommendation["comparables_used"],
            "agent_reasoning": reasoning,
        }


def _mean_similarity(comps: list[dict[str, Any]]) -> float:
    if not comps:
        return 0.0
    return sum(c["similarity_score"] for c in comps) / len(comps)
