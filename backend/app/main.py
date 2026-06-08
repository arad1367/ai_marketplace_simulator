"""FastAPI application entrypoint.

Run locally with::

    uvicorn app.main:app --reload --port 8000

(from the ``backend`` directory, with the virtualenv active).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .routers import admin, simulation

settings = get_settings()

app = FastAPI(
    title="AI Marketplace Simulator API",
    description=(
        "Agent-based pricing simulation with admin-gated raw-data export. "
        "Public users run simulations and view aggregate summaries; only the "
        "researcher (admin) can export raw logs."
    ),
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers (all under /api).
app.include_router(simulation.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health", tags=["health"])
async def health() -> dict:
    """Liveness probe + configuration sanity check."""
    return {
        "status": "ok",
        "version": __version__,
        "env": settings.app_env,
        "supabase_configured": settings.supabase_configured,
    }
