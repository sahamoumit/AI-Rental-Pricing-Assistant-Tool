// Thin fetch wrappers around the FastAPI backend.
// No DOM code here — this module only speaks HTTP/JSON.

const API_BASE = "http://localhost:8001";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    // Surface FastAPI's `detail` when available — /chat 503s carry the
    // remediation command (e.g. "run `ollama serve`") the analyst needs.
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) {
      /* body was not JSON — fall back to statusText */
    }
    throw new Error(`POST ${path} failed: ${res.status} — ${detail}`);
  }
  return res.json();
}

const api = {
  listProperties: () => apiGet("/properties"),
  getProperty: (propertyId) => apiGet(`/properties/${encodeURIComponent(propertyId)}`),
  getComparables: (propertyId) =>
    apiGet(`/properties/${encodeURIComponent(propertyId)}/comparables`),
  getRecommendation: (propertyId) => apiPost("/recommend", { property_id: propertyId }),
  runPricingAgent: (propertyId) => apiPost("/agent/pricing", { property_id: propertyId }),
  recalculateRecommendation: (propertyId, ids) =>
    apiPost("/recommend/recalculate", {
      property_id: propertyId,
      selected_comparable_ids: ids,
    }),
  chat: (propertyId, question, recommendation) =>
    apiPost("/chat", {
      property_id: propertyId,
      question,
      recommendation,
    }),
  submitFeedback: (propertyId, recommendedRent, selectedComparables, feedback) =>
    apiPost("/feedback", {
      property_id: propertyId,
      recommended_rent: recommendedRent,
      selected_comparables: selectedComparables,
      feedback,
    }),
};

window.api = api;
