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
  └── Learning Agent           — reads captured feedback and surfaces structured insights (read-only). Never silently biases pricing; any influence on a recommendation must be explicit, opt-in, and visible in the response.
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
- ✅ **Milestone 5 (AI conversation service):** stateless `POST /chat` backed by a local Llama model via Ollama's HTTP API — no OpenAI dependency. `services/chat.py` pulls the target from `DataLoader`, injects the caller-supplied recommendation into a prompt template on disk (`app/prompts/chat_prompt.txt`, split on `[SYSTEM]`/`[USER]` markers), POSTs to `{OLLAMA_BASE_URL}/api/chat` with `httpx` (no SDK), and returns `{answer, references}` where `references` is a compact projection of `comparables_used`. Chat never recomputes the recommendation — the frontend re-posts the object it received from `/recommend` (or `/recommend/recalculate`), so the analyst's chosen comp set is the source of truth. Errors: 400 (missing/bad body), 404 (unknown property), 503 (Ollama unreachable, model missing, or upstream failure — messages carry the exact remediation command). Env: `OLLAMA_MODEL` (default `llama3.2`), `OLLAMA_BASE_URL` (default `http://localhost:11434`). Verified live end-to-end.
- ✅ **Milestone 5 (frontend wiring):** chat panel wired to `POST /chat`. `ui.js` keeps `lastRecommendation` in module scope — populated by `renderRecommendation` (both `/recommend` and `/recommend/recalculate`), cleared on placeholder/property change. The send button is disabled until a recommendation exists (label switches between `Generate a recommendation first` and `Send`); Enter also submits. Answers render as assistant bubbles with reference chips (`P0091 · Koregaon Park · ₹37,300`) below; failures render as red-tinted error bubbles carrying FastAPI's `detail` field, so a 503 shows "Ollama not reachable — is `ollama serve` running?" in-thread. Transcript clears on property change. No chat history / session memory / streaming. `apiPost` was updated to surface FastAPI's `detail` on non-2xx (benefits `/recommend*` too).
- ✅ **Milestone 6 (analyst feedback service):** stateless `POST /feedback` appends one row per submission to `backend/data/analyst_feedback.csv`. `services/feedback.py` validates ids via `DataLoader`, dedupes the comp list preserving order, rejects the target as its own comparable, and writes an ISO 8601 UTC timestamp + JSON-encoded comp list via `csv.DictWriter`. Header written lazily (only when file missing or 0 bytes). Route enforces the wire contract (types/emptiness/positivity/`bool` explicitly rejected as rent) → 400; service raises `LookupError → 404` (unknown property or comp), `RuntimeError → 500` (CSV I/O). No file locking (prototype single-user). Synthetic seed data preserved as `analyst_feedback.seed.csv` for a future Learning Agent.
- ✅ **Milestone 6 (frontend wiring):** feedback form wired to `POST /feedback`. Submit button disabled until (recommendation exists AND ≥1 comp checked AND non-empty textarea); its label steps through `Generate a recommendation first` → `Select at least one comparable` → `Write feedback first` → `Submit Feedback`. Comps sent = **currently checked** (not `lastRecommendation.comparables_used`), rent sent = `lastRecommendation.recommended_rent`. Success/error render as in-panel banners; textarea clears on success. Property change resets the form. Feedback text does NOT auto-clear on recalculate (the analyst may be typing about the current recommendation).
- ✅ **Milestone 7 (Pricing Agent):** first agent-layer module — `agents/pricing_agent.py`. Stateless `PricingAgent.recommend(property_id, loader)` orchestrates the existing Comparable + Pricing services: loads the target, fetches the top-N comps via `similarity.top_comparables`, evaluates count + mean similarity, and if the mean falls below a configurable `low_confidence_threshold` (default `0.55`, mirrors `pricing._CONFIDENCE_MED`) retries once with a broader search (`n=10`) and hands those exact comp ids to the pricing service. Final rent math is *always* delegated to `services.pricing.calculate_recommended_rent` — the agent never duplicates the formula. Response is the pricing service's payload plus `agent_reasoning: list[str]` (execution trace). Exposed via `POST /agent/pricing` (thin route, same 400/404 mapping as `/recommend`). `/recommend` and `/recommend/recalculate` are unchanged.
- ✅ **Milestone 7 (frontend wiring):** secondary **Run via Pricing Agent** button under the existing "Generate AI Recommendation" (outlined style so the direct path stays the primary CTA). Same recommendation card renders; a new indigo **Agent Reasoning** callout appears with the numbered `agent_reasoning` steps and auto-hides on non-agent responses (e.g. `/recommend`, `/recommend/recalculate`) or property change. `api.js` gains `runPricingAgent(propertyId)`; `ui.js` gains `onRunPricingAgent()` + `renderAgentReasoning()`.
- ⏳ **Not yet built:** Pydantic response models; Property Intelligence, Comparable, Conversation, Learning, Orchestrator agents (Pricing Agent shipped in M7; Comparable, Conversation, and Learning agent wrappers over the underlying services still TBD). No agents wire feedback into pricing or the LLM yet.

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
│   ├── data/
│   │   ├── properties.csv
│   │   ├── rental_history.csv
│   │   ├── analyst_feedback.csv     # Append-only sink for M6 submissions (header at boot)
│   │   └── analyst_feedback.seed.csv # 50 synthetic rows preserved for future Learning Agent
│   └── app/                         # FastAPI app (built incrementally)
│       ├── main.py                  # FastAPI entrypoint (lifespan loads CSVs into app.state)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── properties.py        # Property list + detail + comparables routes
│       │   ├── pricing.py           # POST /recommend (M3) — thin, delegates to services.pricing
│       │   ├── chat.py              # POST /chat (M5) — thin, delegates to services.chat
│       │   ├── feedback.py          # POST /feedback (M6) — thin, delegates to services.feedback
│       │   └── agent.py             # POST /agent/pricing (M7) — thin, delegates to PricingAgent
│       ├── services/
│       │   ├── __init__.py
│       │   ├── data_loader.py       # In-memory CSV access (single source of truth)
│       │   ├── similarity.py        # Weighted similarity + top-N comparables (M2)
│       │   ├── pricing.py           # Rent recommendation (M3) — single entry point calculate_recommended_rent()
│       │   ├── chat.py              # Ollama-backed conversation (M5) — answer_question()
│       │   └── feedback.py          # Append-only CSV writer (M6) — record_feedback()
│       ├── prompts/
│       │   ├── __init__.py          # Package marker
│       │   └── chat_prompt.txt      # System + user template ([SYSTEM]/[USER] split)
│       ├── agents/
│       │   ├── __init__.py
│       │   └── pricing_agent.py     # PricingAgent (M7) — orchestrates similarity + pricing, adds reasoning trace
│       └── models/                  # Pydantic schemas (added as endpoints need them)
├── docs/
├── README.md
└── CLAUDE.md
```

## Tech Stack

- **Frontend**: single static HTML file — Tailwind CSS + Lucide icons over CDN, no framework, no build step.
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic.
- **Data**: pandas, numpy over CSV files.
- **AI**: local Llama via [Ollama](https://ollama.com)'s HTTP API. Called with `httpx` — no SDK. Model + endpoint configurable via `.env`.
- **Config**: python-dotenv (`.env`, never committed).

## Coding Guidelines

**Architecture**
- Clean separation of concerns: `api/` → `services/` → `agents/` → data.
- Frontend and backend stay fully decoupled — the frontend only talks to the backend over JSON.
- Business logic lives in `services/` or `agents/`, never in routes and never in the frontend.
- Each agent has a single responsibility. If an agent grows two jobs, split it.
- **Pricing stays transparent.** The base rent recommendation is deterministic and derivable end-to-end from `services/pricing.py`. Feedback, learning, or any other signal must NOT silently modify it. If a signal ever influences a recommendation, it must be (a) explicitly requested by the caller, (b) surfaced as its own line in `pricing_factors` with a clear note, and (c) skippable — the default path stays pure.

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

### Ollama (required from M5 onward)

`POST /chat` calls a local Llama model via Ollama. Install once, run the daemon, pull the model:

```bash
brew install ollama          # or see https://ollama.com
ollama serve &               # starts the daemon at http://localhost:11434
ollama pull llama3.2         # ~2 GB
```

Everything else runs without secrets. `.env` at `backend/.env` is optional — only needed to override defaults:

- `OLLAMA_MODEL` (default `llama3.2`)
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)

No API keys anywhere. Never commit `.env`.

## What "Done" Looks Like For This Prototype

- Analyst can select a property, see a recommended rent with reasoning and confidence.
- Analyst can view comparables, toggle them, and recalculate.
- Analyst can ask follow-up questions and get grounded answers.
- Analyst can submit feedback that's persisted (CSV is fine).
- The flow works end-to-end on a laptop with sample data. No deployment target.
