"""FastAPI application factory and configuration.

Creates the app with:
- CORS middleware (allows React dev server on localhost:5173).
- Lifespan handler that initializes the SQLite database on startup.
- Route routers for scenarios and simulations.

Run with:
    uvicorn webapp.backend.app:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from webapp.backend.db import init_db
from webapp.backend.routes.datasets import router as datasets_router
from webapp.backend.routes.scenarios import router as scenarios_router
from webapp.backend.routes.simulations import router as simulations_router
from webapp.backend.routes.sweeps import router as sweeps_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB on startup.

    Creates the SQLite database and tables if they don't exist.
    Yields control to the app, then cleans up on shutdown.
    """
    await init_db()
    logging.getLogger(__name__).info("Database initialized")
    yield


app = FastAPI(
    title="Energy Mix Simulator API",
    description=(
        "REST API for Monte Carlo simulation of electricity generation mixes. "
        "Define scenarios, run simulations, and fetch interactive chart data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow React dev server and common local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress responses above ~1 KB — the carbon-intensity country-year
# dataset is ~500 KB of JSON and benefits from >5x compression.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Register route modules
app.include_router(scenarios_router)
app.include_router(simulations_router)
app.include_router(sweeps_router)
app.include_router(datasets_router)


@app.get("/api/health")
async def health_check() -> dict:
    """Simple health check endpoint.

    Returns:
        Dict with status 'ok' and the API version.
    """
    return {"status": "ok", "version": "0.1.0"}
