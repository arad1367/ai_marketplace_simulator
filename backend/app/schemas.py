"""Pydantic request/response models shared across the API.

These mirror the database schema and the contract documented in CLAUDE.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums for the categorical configuration fields                              #
# --------------------------------------------------------------------------- #
class AgentType(str, Enum):
    profit_maximizer = "profit_maximizer"
    revenue_maximizer = "revenue_maximizer"
    market_share_maximizer = "market_share_maximizer"


class InfoVisibility(str, Enum):
    local = "local"
    global_ = "global"
    noisy_global = "noisy_global"


class RegulationMode(str, Enum):
    none = "none"
    soft_cap = "soft_cap"
    penalty_on_collusion = "penalty_on_collusion"


class CoordinationMode(str, Enum):
    independent = "independent"
    shared_model = "shared_model"


class RunStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"


# --------------------------------------------------------------------------- #
# Request models                                                              #
# --------------------------------------------------------------------------- #
class SimulationConfig(BaseModel):
    """Configuration payload for POST /api/run-simulation."""

    num_firms: int = Field(default=3, ge=2, le=10)
    num_consumers: int = Field(default=1000, ge=10, le=100_000)
    num_timesteps: int = Field(default=50, ge=1, le=500)
    random_seed: Optional[int] = Field(default=None, ge=0)
    run_description: str = Field(default="", max_length=2000)

    agent_type: AgentType = AgentType.profit_maximizer
    info_visibility: InfoVisibility = InfoVisibility.global_
    regulation_mode: RegulationMode = RegulationMode.none
    coordination_mode: CoordinationMode = CoordinationMode.independent

    baseline_cost: float = Field(default=6.0, gt=0)
    demand_alpha: float = Field(default=1.0, gt=0)
    collusion_threshold: float = Field(default=0.8, ge=0, le=1)


# --------------------------------------------------------------------------- #
# Response models                                                             #
# --------------------------------------------------------------------------- #
class RunResult(BaseModel):
    """Response for POST /api/run-simulation."""

    run_id: str
    num_rows: int
    status: RunStatus


class RunSummary(BaseModel):
    """Aggregate-only response for GET /api/run/{run_id}/summary."""

    run_id: str
    description: str
    status: RunStatus
    num_firms: int
    num_timesteps: int
    num_rows: int
    agent_type: str
    info_visibility: str
    regulation_mode: str
    coordination_mode: str
    avg_market_price_by_timestep: list[float]
    avg_consumer_surplus_by_timestep: list[float]
    avg_collusion_indicator_by_timestep: list[float]
    total_profit_by_firm: dict[str, float]


class RunListItem(BaseModel):
    """Row in the admin run listing."""

    run_id: str
    created_at: Optional[str] = None
    description: str = ""
    num_firms: int = 0
    num_timesteps: int = 0
    status: str = ""


class LogRow(BaseModel):
    """A single firm/timestep observation (matches simulation_logs)."""

    run_id: str
    timestamp: str
    timestep: int
    firm_id: str
    agent_type: str
    info_visibility: str
    regulation_mode: str
    coordination_mode: str
    price: float
    baseline_cost: float
    units_sold: int
    revenue: float
    profit: float
    market_avg_price: float
    market_price_std: float
    collusion_indicator: float
    consumer_surplus: float
    regulatory_penalty: float
    observed_competitor_prices: dict[str, float]
    agent_internal_state: dict[str, Any]
    agent_decision_reasoning: str
    event_notes: str
