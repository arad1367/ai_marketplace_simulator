"""Market-level metrics: price dispersion and collusion indicators."""

from __future__ import annotations

import numpy as np

# Scale controlling how quickly the collusion indicator decays with price
# distance. Expressed as a fraction of the mean market price.
COLLUSION_SCALE_FRACTION = 0.10


def market_price_stats(prices: np.ndarray) -> tuple[float, float]:
    """Return ``(mean, population_std)`` of firm prices."""
    return float(np.mean(prices)), float(np.std(prices))


def collusion_indicators(prices: np.ndarray) -> np.ndarray:
    """Per-firm collusion indicator in ``[0, 1]``.

    Higher means the firm's price is more similar to its competitors' average,
    i.e. greater price alignment. Computed as an exponential decay of the
    distance between a firm's price and the mean of the *other* firms' prices,
    normalised by the mean market price.
    """
    n = prices.shape[0]
    if n < 2:
        return np.ones(n)

    total = prices.sum()
    competitor_mean = (total - prices) / (n - 1)

    mean_price = float(np.mean(prices))
    scale = max(mean_price * COLLUSION_SCALE_FRACTION, 1e-6)

    distance = np.abs(prices - competitor_mean)
    return np.exp(-distance / scale)
