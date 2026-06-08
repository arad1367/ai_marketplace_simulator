"""Consumer population and demand model.

A population of ``num_consumers`` consumers each hold a heterogeneous
``baseline_quality`` valuation for every firm. At each timestep a consumer
chooses the firm maximising their utility::

    utility_ij = baseline_quality_ij - demand_alpha * price_j

If the best available utility is negative the consumer makes no purchase (an
outside option with utility 0). Vectorised with NumPy so large populations stay
fast.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DemandOutcome:
    """Result of allocating the consumer population across firms."""

    units_sold: np.ndarray        # shape (num_firms,), int
    consumer_surplus: float       # total realised surplus across the population


class ConsumerPopulation:
    """Heterogeneous consumers with per-firm quality valuations."""

    def __init__(
        self,
        num_consumers: int,
        num_firms: int,
        baseline_cost: float,
        rng: np.random.Generator,
    ) -> None:
        self.num_consumers = num_consumers
        self.num_firms = num_firms

        # Quality valuations are centred a little above cost so that a healthy
        # market clears, with consumer-level heterogeneity (normal noise) and a
        # firm-level vertical quality offset (some firms are simply preferred).
        firm_quality_offset = rng.normal(0.0, 0.5, size=num_firms)
        base_level = baseline_cost * 2.0
        self.quality = (
            base_level
            + firm_quality_offset[np.newaxis, :]
            + rng.normal(0.0, 1.0, size=(num_consumers, num_firms))
        )

    def allocate(self, prices: np.ndarray, demand_alpha: float) -> DemandOutcome:
        """Assign each consumer to their utility-maximising firm."""
        # utility matrix: (num_consumers, num_firms)
        utility = self.quality - demand_alpha * prices[np.newaxis, :]

        best_firm = np.argmax(utility, axis=1)
        best_utility = utility[np.arange(self.num_consumers), best_firm]

        # Outside option: no purchase when the best utility is non-positive.
        purchased = best_utility > 0.0
        chosen = best_firm[purchased]

        units_sold = np.bincount(chosen, minlength=self.num_firms).astype(int)
        consumer_surplus = float(best_utility[purchased].sum())

        return DemandOutcome(units_sold=units_sold, consumer_surplus=consumer_surplus)
