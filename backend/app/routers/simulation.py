"""Public simulation endpoints: run a simulation and read aggregate summaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, status

from ..database import SupabaseNotConfiguredError
from ..schemas import RunResult, RunStatus, RunSummary, SimulationConfig
from ..services import fetch_run_record, fetch_summary_series, run_and_persist

router = APIRouter(tags=["simulation"])

# Simulations are CPU-bound and synchronous (Supabase writes). Run them off the
# event loop so the server stays responsive.
_executor = ThreadPoolExecutor(max_workers=2)


@router.post("/run-simulation", response_model=RunResult)
async def run_simulation(config: SimulationConfig) -> RunResult:
    """Run a full simulation and persist run + per-firm/timestep logs."""
    import asyncio

    loop = asyncio.get_running_loop()
    try:
        run_id, num_rows, run_status = await loop.run_in_executor(
            _executor, run_and_persist, config
        )
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {exc}",
        ) from exc

    return RunResult(run_id=run_id, num_rows=num_rows, status=run_status)


@router.get("/run/{run_id}/summary", response_model=RunSummary)
async def run_summary(run_id: str) -> RunSummary:
    """Return aggregate-only statistics for a run (no raw logs)."""
    try:
        record = fetch_run_record(run_id)
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        )

    series = fetch_summary_series(run_id)

    return RunSummary(
        run_id=run_id,
        description=record.get("description") or "",
        status=RunStatus(record.get("status", "completed")),
        num_firms=record.get("num_firms", 0),
        num_timesteps=record.get("num_timesteps", 0),
        num_rows=series["num_rows"],
        agent_type=record.get("agent_type", ""),
        info_visibility=record.get("info_visibility", ""),
        regulation_mode=record.get("regulation_mode", ""),
        coordination_mode=record.get("coordination_mode", ""),
        avg_market_price_by_timestep=series["avg_market_price_by_timestep"],
        avg_consumer_surplus_by_timestep=series["avg_consumer_surplus_by_timestep"],
        avg_collusion_indicator_by_timestep=series["avg_collusion_indicator_by_timestep"],
        total_profit_by_firm=series["total_profit_by_firm"],
    )
