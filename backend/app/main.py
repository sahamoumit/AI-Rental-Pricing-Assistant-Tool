"""FastAPI entrypoint for the AI Rental Pricing Assistant.

Responsibility is narrow: build the app, load data once at startup, wire CORS
for the static frontend, and mount routers. No business logic lives here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, pricing, properties
from app.services.data_loader import DataLoader


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load CSVs once, attach to app.state so routers can reach them via Request.
    loader = DataLoader()
    loader.load()
    app.state.data = loader
    yield


app = FastAPI(
    title="AI Rental Pricing Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# The frontend is served as a static file (e.g. http://localhost:8000/...),
# so the browser origin differs from the API. Permissive CORS is fine for a
# local prototype; tighten before anything ships beyond a laptop.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(properties.router)
app.include_router(pricing.router)
app.include_router(chat.router)
