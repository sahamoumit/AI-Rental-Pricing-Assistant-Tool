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
    throw new Error(`POST ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

const api = {
  listProperties: () => apiGet("/properties"),
  getProperty: (propertyId) => apiGet(`/properties/${encodeURIComponent(propertyId)}`),
  getComparables: (propertyId) =>
    apiGet(`/properties/${encodeURIComponent(propertyId)}/comparables`),
  getRecommendation: (propertyId) => apiPost("/recommend", { property_id: propertyId }),
  recalculateRecommendation: (propertyId, ids) =>
    apiPost("/recommend/recalculate", {
      property_id: propertyId,
      selected_comparable_ids: ids,
    }),
};

window.api = api;
