"""Tests for the simulation engine (no database required)."""

from __future__ import annotations

import math

from app.csv_export import CSV_COLUMNS, iter_csv
from app.schemas import (
    AgentType,
    CoordinationMode,
    InfoVisibility,
    RegulationMode,
    SimulationConfig,
)
from app.simulation import SimulationEngine

REQUIRED_ROW_KEYS = set(CSV_COLUMNS)


def _config(**overrides) -> SimulationConfig:
    base = dict(
        num_firms=3,
        num_consumers=500,
        num_timesteps=20,
        random_seed=42,
        run_description="test run",
    )
    base.update(overrides)
    return SimulationConfig(**base)


def test_row_count_matches_firms_times_steps():
    cfg = _config(num_firms=4, num_timesteps=15)
    out = SimulationEngine(cfg, "run_test").run()
    assert len(out.rows) == 4 * 15


def test_rows_have_all_required_columns():
    out = SimulationEngine(_config(), "run_test").run()
    for row in out.rows:
        assert REQUIRED_ROW_KEYS.issubset(row.keys())


def test_determinism_with_seed():
    a = SimulationEngine(_config(random_seed=7), "run_a").run()
    b = SimulationEngine(_config(random_seed=7), "run_b").run()
    prices_a = [r["price"] for r in a.rows]
    prices_b = [r["price"] for r in b.rows]
    assert prices_a == prices_b


def test_prices_respect_cost_floor_and_ceiling():
    cfg = _config(baseline_cost=6.0)
    out = SimulationEngine(cfg, "run_test").run()
    for row in out.rows:
        assert row["price"] >= 6.0 - 1e-6
        assert row["price"] <= 6.0 * 4.0 + 1e-6


def test_soft_cap_limits_price():
    cfg = _config(regulation_mode=RegulationMode.soft_cap, baseline_cost=6.0)
    out = SimulationEngine(cfg, "run_test").run()
    cap = 6.0 * 2.0  # baseline_cost * (1 + SOFT_CAP_MARGIN_FRACTION)
    for row in out.rows:
        assert row["price"] <= cap + 1e-6


def test_penalty_on_collusion_can_trigger():
    cfg = _config(
        regulation_mode=RegulationMode.penalty_on_collusion,
        coordination_mode=CoordinationMode.shared_model,
        collusion_threshold=0.5,
        num_timesteps=40,
    )
    out = SimulationEngine(cfg, "run_test").run()
    assert any(row["regulatory_penalty"] > 0 for row in out.rows)


def test_local_visibility_hides_competitors():
    cfg = _config(info_visibility=InfoVisibility.local)
    out = SimulationEngine(cfg, "run_test").run()
    for row in out.rows:
        assert row["observed_competitor_prices"] == {}


def test_global_visibility_shows_competitors():
    cfg = _config(info_visibility=InfoVisibility.global_, num_firms=3)
    out = SimulationEngine(cfg, "run_test").run()
    # On a later timestep, each firm should see the other two.
    late_rows = [r for r in out.rows if r["timestep"] == 5]
    for row in late_rows:
        assert len(row["observed_competitor_prices"]) == 2


def test_market_metrics_are_finite():
    out = SimulationEngine(_config(), "run_test").run()
    for row in out.rows:
        assert math.isfinite(row["market_avg_price"])
        assert math.isfinite(row["market_price_std"])
        assert 0.0 <= row["collusion_indicator"] <= 1.0


def test_aggregate_series_lengths():
    cfg = _config(num_timesteps=12)
    out = SimulationEngine(cfg, "run_test").run()
    assert len(out.avg_market_price_by_timestep) == 12
    assert len(out.avg_consumer_surplus_by_timestep) == 12
    assert len(out.avg_collusion_indicator_by_timestep) == 12


def test_reasoning_is_nonempty_text():
    out = SimulationEngine(_config(), "run_test").run()
    assert all(isinstance(r["agent_decision_reasoning"], str) for r in out.rows)
    assert all(len(r["agent_decision_reasoning"]) > 0 for r in out.rows)


def test_all_agent_types_run():
    for at in AgentType:
        out = SimulationEngine(_config(agent_type=at), f"run_{at.value}").run()
        assert len(out.rows) > 0


def test_csv_export_header_and_rows():
    out = SimulationEngine(_config(num_timesteps=3, num_firms=2), "run_csv").run()
    chunks = list(iter_csv(out.rows))
    text = "".join(chunks)
    header = text.splitlines()[0]
    assert header == ",".join(CSV_COLUMNS)
    # header + one line per row
    assert len(text.strip().splitlines()) == 1 + len(out.rows)
