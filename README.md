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

- **Frontend** — single-page UI (Tailwind HTML + a small vanilla-JS layer in `frontend/js/`). Fully wired to the backend for Milestones 1–6: property list + selected-property details, top-5 comparables on demand, a rent recommendation card (rent, price range, confidence pill, "why this price" factor list, timestamp) driven by **Generate AI Recommendation**, analyst-driven **Recalculate Recommendation** (toggle comp checkboxes to include/exclude and re-price with the same math), a live chat panel that asks follow-up questions about the current recommendation, and a feedback form that captures the analyst's take on each recommendation. Every panel talks to a live endpoint — no placeholders remain.
- **Backend** — FastAPI service. Milestones 1–6 are live: loads the CSVs at startup, serves property list/detail endpoints, returns the top-5 comparable properties for any target via a deterministic weighted similarity score, produces a rent recommendation with confidence and price range via a similarity-weighted comp model with area/amenity/location adjustments, re-computes that recommendation over an analyst-supplied comp set, answers analyst questions with a local Llama model that grounds every response in the target property + current recommendation + chosen comparables, and appends analyst feedback (property, rent, chosen comps, free text, ISO 8601 UTC timestamp) to `data/analyst_feedback.csv`.
- **AI layer** — comparable retrieval + a pricing model (both shipped as deterministic services in M2/M3, exposed to analyst edits in M4). A local Llama model (via Ollama's HTTP API) powers the conversational Q&A in M5. Feedback captured in M6 is stored append-only for a future Learning Agent to consume. Dedicated agents (Property Intelligence, Pricing, Conversation, Learning, Orchestrator) still planned as wrappers over these services.

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
│   ├── data/
│   │   ├── properties.csv
│   │   ├── rental_history.csv
│   │   ├── analyst_feedback.csv     # Append-only sink for /feedback submissions
│   │   └── analyst_feedback.seed.csv # Synthetic seed rows preserved for future Learning Agent
│   └── app/                         # FastAPI service
│       ├── main.py                  # Entrypoint (startup hook loads CSVs, mounts routers)
│       ├── api/
│       │   ├── properties.py        # GET /properties, /properties/{id}, /properties/{id}/comparables
│       │   ├── pricing.py           # POST /recommend, POST /recommend/recalculate
│       │   ├── chat.py              # POST /chat
│       │   └── feedback.py          # POST /feedback
│       ├── services/
│       │   ├── data_loader.py       # In-memory CSV access (single source of truth)
│       │   ├── similarity.py        # Weighted similarity scoring + top-N comparables
│       │   ├── pricing.py           # Rent recommendation (weighted comp mean + adjustments + confidence)
│       │   ├── chat.py              # Ollama-backed conversation (grounded in the current recommendation)
│       │   └── feedback.py          # Append-only CSV writer for analyst feedback
│       └── prompts/
│           └── chat_prompt.txt      # System + user template for /chat
├── docs/                            # Design notes, diagrams, decision log
├── CLAUDE.md
└── README.md
```

## Tech Stack

- **Frontend**: Tailwind CSS + Lucide icons — delivered as a single HTML file for zero-build previewing.
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic, pandas.
- **LLM**: local Llama via [Ollama](https://ollama.com)'s HTTP API (default model `llama3.2`, called with `httpx` — no SDK). Powers the conversational Q&A grounded in the current recommendation. Model + endpoint configurable via `.env`.
- **AI / ML (planned)**: replace the deterministic pricing formula with a trained rent model (regression / gradient boosting); agent wrappers around the existing services.
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

### Ollama (needed for chat)

`POST /chat` calls a local Llama model via Ollama. Skip this if you only need M1–M4 or M6 endpoints — `/feedback` is CSV-only and orthogonal to Ollama.

```bash
brew install ollama          # or see https://ollama.com
ollama serve &               # daemon on http://localhost:11434
ollama pull llama3.2         # ~2 GB
```

Defaults are wired for a local install. To override, add a `backend/.env`:

```
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

No API keys are needed — Ollama runs locally, unauthenticated. `.env` is gitignored.

### Implemented endpoints

| Method | Path | Milestone | Description |
|---|---|---|---|
| `GET` | `/health` | 1 | Liveness check. |
| `GET` | `/properties` | 1 | Full property list — powers the selection dropdown. |
| `GET` | `/properties/{property_id}` | 1 | Single-property detail. Returns `404` if unknown. |
| `GET` | `/properties/{property_id}/comparables` | 2 | Top 5 comparables ranked by a weighted similarity score (locality, bedrooms, area, type, bathrooms, amenities). Each result carries a `similarity_score` in `[0, 1]`. Returns `404` if the target is unknown. |
| `POST` | `/recommend` | 3 | Rent recommendation for a target property. Body: `{"property_id": "P0001"}`. Returns `recommended_rent`, `confidence {score, level}`, `price_range {min, max}`, `pricing_factors {base_rent, area_adjustment, amenities_adjustment, location_adjustment, notes[]}`, and `comparables_used[]`. Deterministic — no LLM. Returns `400` if `property_id` is missing, `404` if the target is unknown. |
| `POST` | `/recommend/recalculate` | 4 | Same recommendation shape as `/recommend`, but scored against an analyst-supplied comp set. Body: `{"property_id": "P0001", "selected_comparable_ids": ["P0091", "P0070", ...]}`. Dedupes the id list preserving order. Returns `400` if `property_id`/`selected_comparable_ids` is missing/empty or if the target id is listed as its own comparable; `404` if the target or any comp id is unknown. |
| `POST` | `/chat` | 5 | Answers an analyst question about a specific recommendation using a local Llama model (via Ollama). Body: `{"property_id": "P0001", "question": "why this price?", "recommendation": { ...full response from /recommend or /recommend/recalculate... }}`. Stateless — chat never recomputes the recommendation; the frontend re-posts what it already has. Returns `{answer, references[]}` where `references` is a compact `[{property_id, address, locality, current_rent}, ...]` projection of `comparables_used`. Returns `400` on missing/malformed body fields, `404` if the target property is unknown, `503` if Ollama is unreachable, the model isn't pulled, or the upstream call fails (message carries the exact remediation command). |
| `POST` | `/feedback` | 6 | Records analyst feedback on a recommendation by appending one row to `backend/data/analyst_feedback.csv`. Body: `{"property_id": "P0001", "recommended_rent": 40900, "selected_comparables": ["P0091", "P0070", ...], "feedback": "…"}`. Writes `timestamp` (ISO 8601 UTC), `property_id`, `recommended_rent`, `selected_comparables` (JSON-encoded list), and `feedback`. Dedupes the comp list preserving order. Header is written lazily on first write. Returns `{"success": true, "message": "Feedback recorded for {property_id}"}`. Returns `400` on missing/malformed body, non-positive rent, empty comps, empty feedback, or target listed as its own comparable; `404` if the target or any comp id is unknown; `500` on CSV write failure. No learning loop yet — this is capture only. |

## Future Improvements

- **Learning loop** — mine the accumulated `analyst_feedback.csv` for patterns (repeated concerns about a locality, a rent tier, an amenity), and either update pricing weights or surface suggestions to the analyst. Capture is live; learning is the next step.
- **Agent wrappers** — the underlying services (`similarity`, `pricing`, `chat`, `feedback`) each expose a single-function seam. Wrap them as Property Intelligence, Pricing, Conversation, Learning, and Orchestrator agents to move from "services" to "AI agents" as described in the design.
- **Real pricing model** — train a rent model on historical leases; expose feature importances in the explanation panel.
- **Grounded chat** — RAG over comps, lease history, and neighborhood data so the assistant cites its sources.
- **Analyst-in-the-loop learning** — turn feedback and comp overrides into training signal for the pricing model.
- **Scenario mode** — sliders for occupancy, seasonality, and amenity upgrades to explore price sensitivity.
- **Auth & multi-tenant portfolios** — per-analyst logins, saved views, and audit trail on recommendations.
- **Testing & CI** — unit tests for the pricing service, snapshot tests for the UI, and a lint/type-check pipeline.
