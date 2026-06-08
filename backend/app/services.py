"""Business-logic services: run the simulation and persist results to Supabase.

Keeps the routers thin. All Supabase writes use the service-role client so they
succeed regardless of Row Level Security; RLS still protects direct client
access from the browser.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .database import get_service_client
from .schemas import RunStatus, SimulationConfig
from .simulation import SimulationEngine, SimulationOutput

# Batch size for inserting log rows (keeps each request payload reasonable).
LOG_INSERT_BATCH = 500


def generate_run_id() -> str:
    """Generate a unique run id like ``run_2026_06_08_142530_ab12``."""
    import uuid

    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:4]
    return f"run_{now:%Y_%m_%d_%H%M%S}_{suffix}"


def _config_to_run_record(config: SimulationConfig, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "description": config.run_description,
        "num_firms": config.num_firms,
        "num_consumers": config.num_consumers,
        "num_timesteps": config.num_timesteps,
        "agent_type": config.agent_type.value,
        "info_visibility": config.info_visibility.value,
        "regulation_mode": config.regulation_mode.value,
        "coordination_mode": config.coordination_mode.value,
        "baseline_cost": config.baseline_cost,
        "demand_alpha": config.demand_alpha,
        "collusion_threshold": config.collusion_threshold,
        "random_seed": config.random_seed,
        "status": RunStatus.created.value,
    }


def run_and_persist(config: SimulationConfig) -> tuple[str, int, RunStatus]:
    """Execute a simulation and persist run + logs. Returns identifying info."""
    client = get_service_client()
    run_id = generate_run_id()

    # 1. Create the run record (status: created).
    client.table("simulation_runs").insert(_config_to_run_record(config, run_id)).execute()

    try:
        # 2. Mark running.
        client.table("simulation_runs").update({"status": RunStatus.running.value}).eq(
            "run_id", run_id
        ).execute()

        # 3. Run the model.
        engine = SimulationEngine(config, run_id)
        output: SimulationOutput = engine.run()

        # 4. Persist logs in batches.
        rows = output.rows
        for start in range(0, len(rows), LOG_INSERT_BATCH):
            batch = rows[start : start + LOG_INSERT_BATCH]
            client.table("simulation_logs").insert(batch).execute()

        # 5. Mark completed.
        client.table("simulation_runs").update({"status": RunStatus.completed.value}).eq(
            "run_id", run_id
        ).execute()

        return run_id, len(rows), RunStatus.completed

    except Exception as exc:  # noqa: BLE001 - record failure then re-raise
        client.table("simulation_runs").update(
            {
                "status": RunStatus.failed.value,
                "error_message": str(exc)[:1000],
            }
        ).eq("run_id", run_id).execute()
        raise


def fetch_run_record(run_id: str) -> dict | None:
    client = get_service_client()
    resp = (
        client.table("simulation_runs")
        .select("*")
        .eq("run_id", run_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def fetch_summary_series(run_id: str) -> dict:
    """Aggregate per-timestep series for the public summary endpoint.

    Pulls only the columns needed for aggregation and computes means in Python
    to keep the query simple and portable.
    """
    client = get_service_client()
    resp = (
        client.table("simulation_logs")
        .select(
            "timestep,firm_id,price,consumer_surplus,collusion_indicator,profit"
        )
        .eq("run_id", run_id)
        .order("timestep")
        .execute()
    )
    logs = resp.data or []

    by_step: dict[int, dict[str, list[float]]] = {}
    profit_by_firm: dict[str, float] = {}
    surplus_seen: dict[int, float] = {}

    for row in logs:
        t = row["timestep"]
        bucket = by_step.setdefault(t, {"price": [], "collusion": []})
        bucket["price"].append(float(row["price"]))
        bucket["collusion"].append(float(row["collusion_indicator"]))
        # consumer_surplus is a market-level value duplicated per firm-row.
        surplus_seen[t] = float(row["consumer_surplus"])
        fid = row["firm_id"]
        profit_by_firm[fid] = profit_by_firm.get(fid, 0.0) + float(row["profit"])

    steps = sorted(by_step.keys())
    avg_price = [round(sum(by_step[t]["price"]) / len(by_step[t]["price"]), 4) for t in steps]
    avg_collusion = [
        round(sum(by_step[t]["collusion"]) / len(by_step[t]["collusion"]), 4) for t in steps
    ]
    avg_surplus = [round(surplus_seen[t], 4) for t in steps]

    return {
        "num_rows": len(logs),
        "avg_market_price_by_timestep": avg_price,
        "avg_consumer_surplus_by_timestep": avg_surplus,
        "avg_collusion_indicator_by_timestep": avg_collusion,
        "total_profit_by_firm": {k: round(v, 4) for k, v in profit_by_firm.items()},
    }


def fetch_recent_runs(limit: int = 100) -> list[dict]:
    client = get_service_client()
    resp = (
        client.table("simulation_runs")
        .select("run_id,created_at,description,num_firms,num_timesteps,status")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def iter_log_rows(run_id: str | None = None, page_size: int = 1000):
    """Yield raw log rows page-by-page (memory-efficient streaming export).

    When ``run_id`` is ``None`` this iterates over **every run** in the
    database, ordered by run then timestep then firm — i.e. the single
    combined dataset the researcher exports for analysis. Rows are fetched
    lazily in pages so even millions of rows never load fully into memory.
    """
    client = get_service_client()
    start = 0
    while True:
        query = client.table("simulation_logs").select("*")
        if run_id is not None:
            query = query.eq("run_id", run_id)
        resp = (
            query.order("run_id")
            .order("timestep")
            .order("firm_id")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        yield from rows
        if len(rows) < page_size:
            break
        start += page_size


def fetch_all_logs(run_id: str) -> list[dict]:
    """Fetch all raw log rows for a single run (admin CSV export)."""
    return list(iter_log_rows(run_id))
