"""Simulation orchestrator.

Wires together the pricing agents, consumer population and market metrics into
a discrete-time run, producing one log row per firm per timestep matching the
``simulation_logs`` schema.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..schemas import SimulationConfig
from .agents import PricingAgent
from .consumers import ConsumerPopulation
from .market import collusion_indicators, market_price_stats

# Regulation tuning.
SOFT_CAP_MARGIN_FRACTION = 1.0   # soft_cap => price <= baseline_cost * (1 + this)
PENALTY_REVENUE_FRACTION = 0.25  # penalty = this * revenue when collusion is high
MAX_PRICE_MULTIPLE = 4.0         # absolute ceiling = baseline_cost * this


@dataclass
class SimulationOutput:
    """Everything produced by a run."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    # Pre-computed aggregates so the summary endpoint need not re-scan rows.
    avg_market_price_by_timestep: list[float] = field(default_factory=list)
    avg_consumer_surplus_by_timestep: list[float] = field(default_factory=list)
    avg_collusion_indicator_by_timestep: list[float] = field(default_factory=list)
    total_profit_by_firm: dict[str, float] = field(default_factory=dict)


def _firm_ids(num_firms: int) -> list[str]:
    """Return firm IDs A, B, C, ... (then A1, B1, ... beyond 26)."""
    letters = string.ascii_uppercase
    if num_firms <= len(letters):
        return list(letters[:num_firms])
    ids: list[str] = []
    for i in range(num_firms):
        ids.append(f"{letters[i % 26]}{i // 26}")
    return ids


class SimulationEngine:
    """Runs an agent-based marketplace simulation from a config."""

    def __init__(self, config: SimulationConfig, run_id: str) -> None:
        self.config = config
        self.run_id = run_id
        self.rng = np.random.default_rng(config.random_seed)

        self.firm_ids = _firm_ids(config.num_firms)
        self.baseline_cost = config.baseline_cost
        self.min_price = config.baseline_cost  # never price below cost
        self.max_price = config.baseline_cost * MAX_PRICE_MULTIPLE
        if config.regulation_mode == "soft_cap":
            self.max_price = min(
                self.max_price,
                config.baseline_cost * (1.0 + SOFT_CAP_MARGIN_FRACTION),
            )

        self.agents = [
            PricingAgent(
                firm_id=fid,
                agent_type=config.agent_type.value,
                baseline_cost=self.baseline_cost,
                min_price=self.min_price,
                max_price=self.max_price,
                rng=self.rng,
            )
            for fid in self.firm_ids
        ]

        self.consumers = ConsumerPopulation(
            num_consumers=config.num_consumers,
            num_firms=config.num_firms,
            baseline_cost=self.baseline_cost,
            rng=self.rng,
        )

    # ------------------------------------------------------------------ #
    # Information visibility                                              #
    # ------------------------------------------------------------------ #
    def _observed_prices(self, firm_index: int, prices: np.ndarray) -> dict[str, float]:
        """Competitor prices visible to ``firm_index`` given info_visibility."""
        mode = self.config.info_visibility.value
        observed: dict[str, float] = {}
        if mode == "local":
            return observed  # only own history is visible
        for j, fid in enumerate(self.firm_ids):
            if j == firm_index:
                continue
            value = prices[j]
            if mode == "noisy_global":
                value = value + self.rng.normal(0.0, 0.05 * max(value, 1e-6))
            observed[fid] = round(float(value), 4)
        return observed

    # ------------------------------------------------------------------ #
    # Run                                                                 #
    # ------------------------------------------------------------------ #
    def run(self) -> SimulationOutput:
        out = SimulationOutput()
        total_profit = {fid: 0.0 for fid in self.firm_ids}

        # Prices carried between steps; seeded from agents' initial prices.
        prices = np.array([agent.price for agent in self.agents], dtype=float)
        timestamp = datetime.now(timezone.utc).isoformat()

        for t in range(self.config.num_timesteps):
            first_step = t == 0

            # 1. Each agent decides a price from last-step observations.
            new_prices = np.empty(self.config.num_firms, dtype=float)
            reasonings: list[str] = []
            observed_list: list[dict[str, float]] = []
            for i, agent in enumerate(self.agents):
                observed = self._observed_prices(i, prices)
                observed_list.append(observed)
                price, reasoning = agent.decide_price(
                    observed_competitor_prices=observed,
                    coordination_mode=self.config.coordination_mode.value,
                    first_step=first_step,
                )
                new_prices[i] = price
                reasonings.append(reasoning)
            prices = new_prices

            # 2. Demand & consumer surplus.
            demand = self.consumers.allocate(prices, self.config.demand_alpha)
            units = demand.units_sold
            revenue = prices * units
            gross_profit = (prices - self.baseline_cost) * units

            # 3. Market metrics.
            market_avg, market_std = market_price_stats(prices)
            collusion = collusion_indicators(prices)

            # 4. Regulation: penalty on collusion (applied to profit).
            penalties = np.zeros(self.config.num_firms, dtype=float)
            if self.config.regulation_mode == "penalty_on_collusion":
                over = collusion > self.config.collusion_threshold
                penalties = np.where(
                    over, PENALTY_REVENUE_FRACTION * revenue, 0.0
                )
            net_profit = gross_profit - penalties

            # 5. Per-step aggregates.
            out.avg_market_price_by_timestep.append(round(market_avg, 4))
            out.avg_consumer_surplus_by_timestep.append(
                round(demand.consumer_surplus, 4)
            )
            out.avg_collusion_indicator_by_timestep.append(
                round(float(np.mean(collusion)), 4)
            )

            # 6. Emergent-event detection (qualitative note for Study 2).
            event_note = self._event_note(t, collusion, market_std)

            # 7. Build log rows and update agent memory.
            for i, agent in enumerate(self.agents):
                agent.record_outcome(
                    units=int(units[i]),
                    revenue=float(revenue[i]),
                    profit=float(net_profit[i]),
                )
                total_profit[agent.firm_id] += float(net_profit[i])
                out.rows.append(
                    self._build_row(
                        timestamp=timestamp,
                        timestep=t,
                        firm_index=i,
                        price=float(prices[i]),
                        units=int(units[i]),
                        revenue=float(revenue[i]),
                        profit=float(net_profit[i]),
                        market_avg=market_avg,
                        market_std=market_std,
                        collusion=float(collusion[i]),
                        consumer_surplus=demand.consumer_surplus,
                        penalty=float(penalties[i]),
                        observed=observed_list[i],
                        reasoning=reasonings[i],
                        event_note=event_note,
                    )
                )

        out.total_profit_by_firm = {k: round(v, 4) for k, v in total_profit.items()}
        return out

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _event_note(self, t: int, collusion: np.ndarray, market_std: float) -> str:
        if t == 0:
            return ""
        all_raised = all(agent.raised_this_step for agent in self.agents)
        high_alignment = float(np.mean(collusion)) > self.config.collusion_threshold
        if all_raised and high_alignment and market_std < self.baseline_cost * 0.1:
            return "Emergent synchronized price increase across all firms."
        if high_alignment:
            return "High price alignment among firms."
        return ""

    def _build_row(
        self,
        *,
        timestamp: str,
        timestep: int,
        firm_index: int,
        price: float,
        units: int,
        revenue: float,
        profit: float,
        market_avg: float,
        market_std: float,
        collusion: float,
        consumer_surplus: float,
        penalty: float,
        observed: dict[str, float],
        reasoning: str,
        event_note: str,
    ) -> dict[str, Any]:
        agent = self.agents[firm_index]
        cfg = self.config
        return {
            "run_id": self.run_id,
            "timestamp": timestamp,
            "timestep": timestep,
            "firm_id": agent.firm_id,
            "agent_type": cfg.agent_type.value,
            "info_visibility": cfg.info_visibility.value,
            "regulation_mode": cfg.regulation_mode.value,
            "coordination_mode": cfg.coordination_mode.value,
            "price": round(price, 4),
            "baseline_cost": round(self.baseline_cost, 4),
            "units_sold": int(units),
            "revenue": round(revenue, 4),
            "profit": round(profit, 4),
            "market_avg_price": round(market_avg, 4),
            "market_price_std": round(market_std, 4),
            "collusion_indicator": round(collusion, 4),
            "consumer_surplus": round(consumer_surplus, 4),
            "regulatory_penalty": round(penalty, 4),
            "observed_competitor_prices": observed,
            "agent_internal_state": agent.internal_state(),
            "agent_decision_reasoning": reasoning,
            "event_notes": event_note,
        }
