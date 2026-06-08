"""AI pricing agents.

Each firm is controlled by a heuristic pricing agent that adjusts its price
based on its own history and (optionally) observed competitor prices. The
agents use a hill-climbing strategy: keep moving the price in the current
direction while the objective improves; reverse direction when it worsens.

Three objectives are supported, matching ``agent_type``:

* ``profit_maximizer``      – objective = profit
* ``revenue_maximizer``     – objective = revenue
* ``market_share_maximizer``– objective = units sold

Information visibility (``info_visibility``) controls what competitor prices the
agent can see, and ``coordination_mode`` controls whether agents nudge toward a
shared market reference (which can foster emergent, synchronized pricing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Tunable behavioural constants.
PRICE_STEP_FRACTION = 0.03          # base step size as a fraction of price
EXPLORATION_NOISE_FRACTION = 0.01   # small random jitter to break ties
IMPROVEMENT_TOLERANCE = 1e-6        # below this, treat objective as unchanged
COMPETITOR_PULL = 0.15             # how strongly to anchor to competitor mean
SHARED_MODEL_PULL = 0.10           # extra anchoring under shared_model


@dataclass
class PricingAgent:
    """A single firm's pricing agent with internal memory."""

    firm_id: str
    agent_type: str
    baseline_cost: float
    min_price: float
    max_price: float
    rng: np.random.Generator

    # --- internal state (logged each step as agent_internal_state) ---
    price: float = 0.0
    last_price: float = 0.0
    last_profit: float = 0.0
    last_revenue: float = 0.0
    last_units: int = 0
    last_objective: float = float("-inf")
    # +1 means "moving up", -1 means "moving down".
    direction: int = 1
    raised_this_step: bool = False

    def __post_init__(self) -> None:
        if self.price <= 0:
            # Start near a modest margin above cost.
            self.price = round(self.baseline_cost * 1.4, 4)
        self.last_price = self.price
        # Start by exploring upward unless told otherwise.
        self.direction = 1 if self.rng.random() > 0.5 else -1

    # ------------------------------------------------------------------ #
    # Objective selection                                                #
    # ------------------------------------------------------------------ #
    def _current_objective(self) -> float:
        if self.agent_type == "revenue_maximizer":
            return self.last_revenue
        if self.agent_type == "market_share_maximizer":
            return float(self.last_units)
        return self.last_profit  # profit_maximizer (default)

    # ------------------------------------------------------------------ #
    # Decision                                                           #
    # ------------------------------------------------------------------ #
    def decide_price(
        self,
        observed_competitor_prices: dict[str, float],
        coordination_mode: str,
        first_step: bool,
    ) -> tuple[float, str]:
        """Choose a new price; return ``(price, reasoning)``."""
        objective = self._current_objective()
        step = self.price * PRICE_STEP_FRACTION

        if first_step:
            reasoning = (
                f"Initial period: set exploratory price of {self.price:.2f}, "
                f"a modest margin above cost ({self.baseline_cost:.2f})."
            )
            new_price = self.price
        else:
            improved = objective > self.last_objective + IMPROVEMENT_TOLERANCE
            if improved:
                # Keep pushing in the same direction.
                reasoning = self._reasoning_improved(objective)
            else:
                # Objective stalled or fell: reverse course.
                self.direction *= -1
                reasoning = self._reasoning_worsened(objective)
            new_price = self.price + self.direction * step

        # Anchor toward competitors when their prices are visible.
        new_price, anchor_note = self._apply_competitor_anchor(
            new_price, observed_competitor_prices, coordination_mode
        )
        if anchor_note:
            reasoning += " " + anchor_note

        # Small exploration noise keeps dynamics from freezing.
        new_price += self.rng.normal(0.0, self.price * EXPLORATION_NOISE_FRACTION)

        # Enforce price bounds.
        new_price = float(np.clip(new_price, self.min_price, self.max_price))

        self.raised_this_step = new_price > self.price + IMPROVEMENT_TOLERANCE
        self.last_objective = objective
        self.last_price = self.price
        self.price = round(new_price, 4)
        return self.price, reasoning

    def _apply_competitor_anchor(
        self,
        price: float,
        observed: dict[str, float],
        coordination_mode: str,
    ) -> tuple[float, str]:
        if not observed:
            return price, ""
        comp_mean = float(np.mean(list(observed.values())))
        pull = COMPETITOR_PULL
        note = ""
        if coordination_mode == "shared_model":
            pull += SHARED_MODEL_PULL
            note = "Coordinated (shared model): nudged toward the market reference price."
        else:
            note = "Adjusted partly toward observed competitor average."
        anchored = price + pull * (comp_mean - price)
        return anchored, note

    # ------------------------------------------------------------------ #
    # Reasoning text (qualitative trace for Study 2)                      #
    # ------------------------------------------------------------------ #
    def _objective_label(self) -> str:
        return {
            "profit_maximizer": "profit",
            "revenue_maximizer": "revenue",
            "market_share_maximizer": "market share",
        }.get(self.agent_type, "profit")

    def _reasoning_improved(self, objective: float) -> str:
        verb = "raising" if self.direction > 0 else "lowering"
        return (
            f"Last period {self._objective_label()} improved "
            f"({self.last_objective:.1f} -> {objective:.1f}); continuing to "
            f"{verb} price to push further in the same direction."
        )

    def _reasoning_worsened(self, objective: float) -> str:
        verb = "raise" if self.direction > 0 else "lower"
        return (
            f"Last period {self._objective_label()} did not improve "
            f"({self.last_objective:.1f} -> {objective:.1f}); reversing course "
            f"to {verb} price instead."
        )

    # ------------------------------------------------------------------ #
    # State snapshot for logging                                          #
    # ------------------------------------------------------------------ #
    def internal_state(self) -> dict[str, Any]:
        return {
            "last_price": round(self.last_price, 4),
            "last_profit": round(self.last_profit, 4),
            "last_revenue": round(self.last_revenue, 4),
            "last_units": int(self.last_units),
            "direction": int(self.direction),
        }

    def record_outcome(self, units: int, revenue: float, profit: float) -> None:
        """Store the realised outcome so the next decision can react to it."""
        self.last_units = int(units)
        self.last_revenue = float(revenue)
        self.last_profit = float(profit)


@dataclass
class AgentObservation:
    """Competitor prices an agent is allowed to see this step."""

    prices: dict[str, float] = field(default_factory=dict)
