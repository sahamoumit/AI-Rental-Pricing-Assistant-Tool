# AI Rental Pricing Assistant

An AI-powered decision-support tool that helps rental analysts price residential properties using comparable listings, market signals, and an explainable recommendation model. Built as a Forward Deployed Software Engineer (FDSE) interview project.

## Project Overview

Rental pricing is typically a slow, manual process — analysts stitch together comps, amenity comparisons, and market intuition across spreadsheets. This project prototypes an assistant that:

- Recommends a monthly rent for a selected property with a confidence score.
- Surfaces the comparable properties and reasoning behind the number.
- Lets analysts interrogate the recommendation through a chat interface and submit structured feedback.

The goal is to keep the analyst in the loop while cutting time-to-decision from hours to minutes.

## Features

- **Property selection** — search and pick a property from the portfolio, with key attributes (bedrooms, bathrooms, area, amenities) at a glance.
- **AI rent recommendation** — a single recommended monthly rent with a confidence badge and bullet-point reasoning.
- **Comparable properties** — ranked comps with similarity scores, distance, and neighborhood tags (schools, metro, parks); analysts can include/exclude comps and recalculate.
- **Conversational Q&A** — chat panel to ask *why* behind the recommendation and probe assumptions.
- **Analyst feedback loop** — free-text feedback capture on each recommendation for downstream model tuning.

## AI Workflow

```
   Property + Attributes
           │
           ▼
   Retrieve Comparables ──► Filter by geo, size, amenities, recency
           │
           ▼
   Score & Weight Comps  ──► Similarity scoring (94%, 89%, ...)
           │
           ▼
   Price Model           ──► Weighted rent + market signals (metro, schools, walkability)
           │
           ▼
   Explanation Layer     ──► Reasoning bullets + confidence score
           │
           ▼
   Analyst Review        ──► Chat Q&A + feedback → training signal
```

1. **Retrieval** — pull candidate comps within a geographic and structural window of the target property.
2. **Similarity scoring** — rank comps on unit type, size, amenities, and location features.
3. **Pricing** — weighted aggregation over the top comps, adjusted for neighborhood signals.
4. **Explanation** — surface the drivers (school zone, metro proximity, low crime) alongside the price.
5. **Feedback** — analyst comments and comp overrides feed back into future recommendations.

## Architecture

```
┌────────────────────┐        ┌────────────────────┐        ┌────────────────────┐
│  Frontend UI       │ ─────► │  Backend API       │ ─────► │  Pricing / LLM     │
│  ai_pricing_       │        │  FastAPI           │        │  Services          │
│  assistant.html    │ ◄───── │  (implemented)     │ ◄───── │  (planned)         │
└────────────────────┘        └────────────────────┘        └────────────────────┘
```

- **Frontend** — single-page UI (Tailwind HTML + a small vanilla-JS layer in `frontend/js/`). Wired to the backend for Milestones 1–4: property list + selected-property details, top-5 comparables on demand, a rent recommendation card (rent, price range, confidence pill, "why this price" factor list, timestamp) driven by **Generate AI Recommendation**, and analyst-driven **Recalculate Recommendation** — toggle comp checkboxes to include/exclude and re-price with the same math. The chat panel and feedback form still show placeholder content until the corresponding backend milestones land.
- **Backend** — FastAPI service. Milestones 1–4 are live: loads the CSVs at startup, serves property list/detail endpoints, returns the top-5 comparable properties for any target via a deterministic weighted similarity score, produces a rent recommendation with confidence and price range via a similarity-weighted comp model with area/amenity/location adjustments, and re-computes that recommendation over an analyst-supplied comp set. Chat and feedback endpoints come in later milestones.
- **AI layer** — comparable retrieval + a pricing model (both shipped as deterministic services in M2/M3, exposed to analyst edits in M4), to be wrapped by dedicated agents and an LLM-driven explanation + chat interface (planned).

## Folder Structure

```
Pricing Assistant/
├── frontend/
│   ├── ai_pricing_assistant.html    # Tailwind single-page UI prototype
│   └── js/
│       ├── api.js                   # fetch() wrappers around the FastAPI endpoints
│       └── ui.js                    # DOM updates + dropdown/details/comparables wiring
├── backend/
│   ├── requirements.txt
│   ├── generate_data.py             # Synthetic CSV generator (Pune data)
│   ├── data/                        # properties/rental_history/analyst_feedback CSVs
│   └── app/                         # FastAPI service
│       ├── main.py                  # Entrypoint (startup hook loads CSVs, mounts routers)
│       ├── api/
│       │   ├── properties.py        # GET /properties, /properties/{id}, /properties/{id}/comparables
│       │   └── pricing.py           # POST /recommend
│       └── services/
│           ├── data_loader.py       # In-memory CSV access (single source of truth)
│           ├── similarity.py        # Weighted similarity scoring + top-N comparables
│           └── pricing.py           # Rent recommendation (weighted comp mean + adjustments + confidence)
├── docs/                            # Design notes, diagrams, decision log
├── CLAUDE.md
└── README.md
```

## Tech Stack

- **Frontend**: Tailwind CSS + Lucide icons — delivered as a single HTML file for zero-build previewing.
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic, pandas.
- **AI / ML (planned)**: comparable-property retrieval + a regression/gradient-boosted pricing model; LLM for explanation and Q&A.
- **Data**: CSV files under `backend/data/` for the prototype (PostgreSQL / vector store are future work).

## Setup

### Backend

Requires Python 3.11+.

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
# API now on http://127.0.0.1:8001
# (Port 8001 so the static frontend server can keep the default 8000.)
```

CSV data is loaded once at startup and kept in memory via the `DataLoader` service.

### Frontend

Static file, no build step.

```bash
cd frontend
python3 -m http.server 8000
# then visit http://localhost:8000/ai_pricing_assistant.html
```

The page calls the backend at `http://localhost:8001`, so start the backend first — otherwise the dropdown will stay on its "Loading properties…" placeholder.

### Implemented endpoints

| Method | Path | Milestone | Description |
|---|---|---|---|
| `GET` | `/health` | 1 | Liveness check. |
| `GET` | `/properties` | 1 | Full property list — powers the selection dropdown. |
| `GET` | `/properties/{property_id}` | 1 | Single-property detail. Returns `404` if unknown. |
| `GET` | `/properties/{property_id}/comparables` | 2 | Top 5 comparables ranked by a weighted similarity score (locality, bedrooms, area, type, bathrooms, amenities). Each result carries a `similarity_score` in `[0, 1]`. Returns `404` if the target is unknown. |
| `POST` | `/recommend` | 3 | Rent recommendation for a target property. Body: `{"property_id": "P0001"}`. Returns `recommended_rent`, `confidence {score, level}`, `price_range {min, max}`, `pricing_factors {base_rent, area_adjustment, amenities_adjustment, location_adjustment, notes[]}`, and `comparables_used[]`. Deterministic — no LLM. Returns `400` if `property_id` is missing, `404` if the target is unknown. |
| `POST` | `/recommend/recalculate` | 4 | Same recommendation shape as `/recommend`, but scored against an analyst-supplied comp set. Body: `{"property_id": "P0001", "selected_comparable_ids": ["P0091", "P0070", ...]}`. Dedupes the id list preserving order. Returns `400` if `property_id`/`selected_comparable_ids` is missing/empty or if the target id is listed as its own comparable; `404` if the target or any comp id is unknown. |

## Future Improvements

- **Wire the remaining panels** — the property list, details, comparables grid, recommendation card, and `Recalculate Recommendation` are all live-wired; the chat panel and feedback form still need backend endpoints (conversation and learning agents) before they can leave placeholder content.
- **Real pricing model** — train a rent model on historical leases; expose feature importances in the explanation panel.
- **Grounded chat** — RAG over comps, lease history, and neighborhood data so the assistant cites its sources.
- **Analyst-in-the-loop learning** — turn feedback and comp overrides into training signal for the pricing model.
- **Scenario mode** — sliders for occupancy, seasonality, and amenity upgrades to explore price sensitivity.
- **Auth & multi-tenant portfolios** — per-analyst logins, saved views, and audit trail on recommendations.
- **Testing & CI** — unit tests for the pricing service, snapshot tests for the UI, and a lint/type-check pipeline.
