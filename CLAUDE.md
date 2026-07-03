# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**AI Rental Pricing Assistant** — FDSE interview prototype.

An AI-assisted tool for rental pricing analysts. It recommends monthly rents from property data, comparable listings, and external location signals. Analysts can chat with the assistant, edit the comparable set, get updated recommendations, and submit feedback that flows back into learning.

This is an **interview prototype**, not a production system. Favor clarity and a working end-to-end flow over robustness, scale, or feature depth.

## Architecture

```
Frontend (HTML / CSS / JS)
        │  REST / JSON
        ▼
Backend (FastAPI)
        │
        ▼
Agent layer
  ├── Orchestrator Agent       — routes requests, coordinates other agents
  ├── Property Intelligence    — enriches a property with location/context signals
  ├── Comparable Agent         — retrieves and scores comparable listings
  ├── Pricing Agent            — produces the rent recommendation + confidence
  ├── Conversation Agent       — handles analyst Q&A over the recommendation
  └── Learning Agent           — captures feedback and prepares training signal
        │
        ▼
Sample data (CSV files)
```

Data lives in CSVs for the prototype — no database. Agents are plain Python classes/modules invoked by services, not a heavy framework.

## Current Status

- ✅ **Milestone 1 (backend foundation):** CSV data loader, FastAPI app, `GET /properties`, `GET /properties/{id}`, `/health`, CORS. Live and verified locally.
- ✅ **Milestone 2 (comparable property service):** deterministic similarity service (`services/similarity.py`) with hand-tuned weighted score over locality, bedrooms, area, type, bathrooms, and amenities. Exposed via `GET /properties/{id}/comparables` → top 5 comps. No LLM, no pricing.
- ✅ **Milestone 2 (frontend wiring):** vanilla JS in `frontend/js/api.js` + `frontend/js/ui.js` fetches `/properties`, populates the dropdown, renders selected-property details, and renders top-5 comparables (with `similarity_score` as an `XX% match` badge) on the "Find Comparables" click.
- ✅ **Milestone 3 (rent recommendation service):** deterministic pricing service (`services/pricing.py`) — similarity-weighted mean of top-5 comp rents, plus small adjustments for area, amenities (`parking`/`balcony`/`gym`/`swimming_pool`/`lift`), and location (`school_rating`, `walkability_score`). Confidence is the mean similarity of the comps; price range widens inversely to confidence. Single public entry point `calculate_recommended_rent(property_id, loader)` — a future Pricing Agent will call it directly. Exposed via `POST /recommend` with body `{"property_id": "..."}`. Returns `recommended_rent`, `confidence {score, level}`, `price_range {min, max}`, `pricing_factors {base_rent, area_adjustment, amenities_adjustment, location_adjustment, notes[]}`, and `comparables_used[]`. No LLM.
- ✅ **Milestone 3 (frontend wiring):** the "AI Recommendation" card is now live — a **Generate AI Recommendation** button POSTs to `/recommend` and renders the rent number, price range, colour-bucketed confidence pill (green/amber/red for high/medium/low), the factor `notes` as "Why this price" bullets, and a fresh timestamp. Card resets on property change.
- ✅ **Milestone 4 (analyst recalculation):** `calculate_recommended_rent` gained an optional `comparable_ids` parameter so the same math applies to an analyst-chosen comp set. Exposed via `POST /recommend/recalculate` with body `{"property_id": "...", "selected_comparable_ids": [...]}`. Same response shape as `/recommend`. Validates existence of every id; distinguishes `LookupError → 404` (unknown property or comp) from `ValueError → 400` (empty list, target as own comp). Both pricing routes updated to that error mapping.
- ✅ **Milestone 4 (frontend wiring):** each comp card carries a `data-comp-card` wrapper and its checkbox a `data-comp-id`. Toggling flips the card ring/bg and re-computes the **Recalculate Recommendation** button's label (`Recalculate with N comparables` / `Select at least one comparable` / default). Click POSTs the checked ids to `/recommend/recalculate` and re-renders the AI Recommendation card via the same renderer as `/recommend`.
- ⏳ **Not yet built:** Pydantic response models; Property Intelligence, Pricing, Conversation, Learning, Orchestrator agents (the Comparable *Agent* wrapper and Pricing *Agent* wrapper are also still TBD — M2–M4 shipped the underlying services only); chat and feedback endpoints + their frontend wiring.

## Folder Structure

```
Pricing Assistant/
├── frontend/
│   ├── ai_pricing_assistant.html    # Single-page UI prototype (Tailwind + Lucide)
│   └── js/
│       ├── api.js                   # fetch() wrappers around the FastAPI endpoints
│       └── ui.js                    # DOM updates + dropdown/details/comparables wiring
├── backend/
│   ├── requirements.txt
│   ├── generate_data.py             # Synthetic CSV generator (Pune data)
│   ├── data/                        # CSV sample data (properties, rental_history, analyst_feedback)
│   └── app/                         # FastAPI app (built incrementally)
│       ├── main.py                  # FastAPI entrypoint (lifespan loads CSVs into app.state)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── properties.py        # Property list + detail + comparables routes
│       │   └── pricing.py           # POST /recommend (M3) — thin, delegates to services.pricing
│       ├── services/
│       │   ├── __init__.py
│       │   ├── data_loader.py       # In-memory CSV access (single source of truth)
│       │   ├── similarity.py        # Weighted similarity + top-N comparables (M2)
│       │   └── pricing.py           # Rent recommendation (M3) — single entry point calculate_recommended_rent()
│       ├── agents/                  # One module per agent (planned)
│       └── models/                  # Pydantic schemas (added as endpoints need them)
├── docs/
├── README.md
└── CLAUDE.md
```

## Tech Stack

- **Frontend**: single static HTML file — Tailwind CSS + Lucide icons over CDN, no framework, no build step.
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic.
- **Data**: pandas, numpy over CSV files.
- **AI**: OpenAI SDK for the LLM-driven agents.
- **Config**: python-dotenv (`.env`, never committed).

## Coding Guidelines

**Architecture**
- Clean separation of concerns: `api/` → `services/` → `agents/` → data.
- Frontend and backend stay fully decoupled — the frontend only talks to the backend over JSON.
- Business logic lives in `services/` or `agents/`, never in routes and never in the frontend.
- Each agent has a single responsibility. If an agent grows two jobs, split it.

**Code style**
- Small functions, readable names, type hints on public functions.
- Pydantic models for every request/response boundary.
- Prefer readability over clever one-liners.
- Comment only where the *why* is non-obvious. Don't restate what the code does.
- Modular and reusable — but don't pre-abstract for hypothetical needs.

**Scope**
- Prototype-grade: pick the simple implementation over the production one.
- No premature auth, caching, retries, or observability unless asked.
- Sample data stays in CSVs until there's a concrete reason to move to a DB.

## Working With This Repo

When generating or editing code:

- **Modify only the files that were requested.** Don't touch unrelated files.
- **Preserve the existing structure and naming.** Don't reorganize without being asked.
- **Explain major design decisions before large code changes.** For anything beyond a small edit, briefly state the approach and trade-off first.
- **Build incrementally.** Ship a small vertical slice end-to-end before broadening.
- **Never rewrite a file wholesale to make a small change.** Prefer targeted edits.
- **Match the prototype's altitude.** Skip enterprise patterns (DI containers, repository interfaces, complex error hierarchies) unless the task requires them.

## Running Locally

Backend and frontend both default to port 8000, so use different ports for them.

```bash
# Backend (port 8001)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend (static, no build, port 8000)
cd frontend
python3 -m http.server 8000
# open http://localhost:8000/ai_pricing_assistant.html
```

Milestone 1 endpoints don't need any secrets. Once agent milestones land, put an `.env` at `backend/.env` with at least `OPENAI_API_KEY`. Never commit it.

## What "Done" Looks Like For This Prototype

- Analyst can select a property, see a recommended rent with reasoning and confidence.
- Analyst can view comparables, toggle them, and recalculate.
- Analyst can ask follow-up questions and get grounded answers.
- Analyst can submit feedback that's persisted (CSV is fine).
- The flow works end-to-end on a laptop with sample data. No deployment target.
