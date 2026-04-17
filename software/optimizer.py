"""Scikit-learn-backed profitability optimizer.

Given a rig and a slate of candidate coins, rank them by predicted
profit per day. When no trained model is provided, the optimizer falls
back to the analytic profitability formula from :mod:`software.profitability`.

A trained model lets you adjust that ground truth for factors the
analytic formula can't see on its own — e.g. pool fees, orphan rates,
price volatility, or observed hashrate drift.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.base import RegressorMixin
from sklearn.linear_model import LinearRegression

from .profitability import (
    Coin,
    Rig,
    electricity_cost_per_day,
    expected_coins_per_day,
    expected_profit_per_day,
    expected_revenue_per_day,
)

FEATURE_NAMES = (
    "hashrate_hs",
    "power_watts",
    "price_usd",
    "network_hashrate_hs",
    "block_reward",
    "block_time_seconds",
    "electricity_cost_per_kwh",
    "analytic_profit_per_day",
)


def featurize(
    rig: Rig, coin: Coin, electricity_cost_per_kwh: float
) -> np.ndarray:
    """Build a 1-D feature vector in the order of :data:`FEATURE_NAMES`."""
    return np.array(
        [
            rig.hashrate_hs,
            rig.power_watts,
            coin.price_usd,
            coin.network_hashrate_hs,
            coin.block_reward,
            coin.block_time_seconds,
            electricity_cost_per_kwh,
            expected_profit_per_day(rig, coin, electricity_cost_per_kwh),
        ],
        dtype=float,
    )


@dataclass(frozen=True)
class Ranking:
    """A single row of the ranked output."""

    coin: Coin
    predicted_profit_per_day: float
    analytic_profit_per_day: float

    @property
    def symbol(self) -> str:
        return self.coin.symbol


class ProfitabilityOptimizer:
    """Rank candidate coins by predicted daily profit.

    Parameters
    ----------
    model:
        Any fitted scikit-learn regressor. If ``None``, predictions fall
        back to the analytic profit formula.
    """

    def __init__(self, model: RegressorMixin | None = None) -> None:
        self.model = model

    def fit(
        self,
        samples: Sequence[tuple[Rig, Coin, float]],
        observed_profit_per_day: Sequence[float],
    ) -> ProfitabilityOptimizer:
        """Fit a simple linear model on (features -> observed profit)."""
        if len(samples) != len(observed_profit_per_day):
            raise ValueError("samples and targets must have the same length")
        if len(samples) < 2:
            raise ValueError("need at least 2 samples to fit a model")
        x = np.vstack(
            [featurize(rig, coin, cost) for rig, coin, cost in samples]
        )
        y = np.asarray(observed_profit_per_day, dtype=float)
        self.model = LinearRegression().fit(x, y)
        return self

    def predict(
        self, rig: Rig, coin: Coin, electricity_cost_per_kwh: float
    ) -> float:
        """Predicted daily profit for a single (rig, coin, cost) tuple."""
        analytic = expected_profit_per_day(rig, coin, electricity_cost_per_kwh)
        if self.model is None:
            return analytic
        x = featurize(rig, coin, electricity_cost_per_kwh).reshape(1, -1)
        return float(self.model.predict(x)[0])

    def rank(
        self,
        rig: Rig,
        coins: Iterable[Coin],
        electricity_cost_per_kwh: float,
    ) -> list[Ranking]:
        """Return coins ranked from most to least profitable."""
        rankings = [
            Ranking(
                coin=coin,
                predicted_profit_per_day=self.predict(
                    rig, coin, electricity_cost_per_kwh
                ),
                analytic_profit_per_day=expected_profit_per_day(
                    rig, coin, electricity_cost_per_kwh
                ),
            )
            for coin in coins
        ]
        rankings.sort(key=lambda r: r.predicted_profit_per_day, reverse=True)
        return rankings

    def best(
        self,
        rig: Rig,
        coins: Iterable[Coin],
        electricity_cost_per_kwh: float,
    ) -> Ranking:
        """Return the single highest-predicted-profit coin."""
        ranked = self.rank(rig, coins, electricity_cost_per_kwh)
        if not ranked:
            raise ValueError("no candidate coins provided")
        return ranked[0]


__all__ = [
    "FEATURE_NAMES",
    "ProfitabilityOptimizer",
    "Ranking",
    "featurize",
    "electricity_cost_per_day",
    "expected_coins_per_day",
    "expected_profit_per_day",
    "expected_revenue_per_day",
]
