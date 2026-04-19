from __future__ import annotations

import math

import pytest

from software.optimizer import (
    FEATURE_NAMES,
    ProfitabilityOptimizer,
    featurize,
)
from software.profitability import Coin, Rig, expected_profit_per_day


@pytest.fixture
def rig() -> Rig:
    return Rig(hashrate_hs=100e12, power_watts=3250)


@pytest.fixture
def coins() -> list[Coin]:
    return [
        Coin(
            symbol="BTC",
            price_usd=60_000.0,
            network_hashrate_hs=500e18,
            block_reward=3.125,
            block_time_seconds=600.0,
        ),
        Coin(
            symbol="LTC",
            price_usd=80.0,
            network_hashrate_hs=800e12,
            block_reward=6.25,
            block_time_seconds=150.0,
        ),
    ]


def test_featurize_length_matches_feature_names(
    rig: Rig, coins: list[Coin]
) -> None:
    assert len(featurize(rig, coins[0], 0.10)) == len(FEATURE_NAMES)


def test_default_predict_matches_analytic_profit(
    rig: Rig, coins: list[Coin]
) -> None:
    optimizer = ProfitabilityOptimizer()
    for coin in coins:
        assert math.isclose(
            optimizer.predict(rig, coin, 0.10),
            expected_profit_per_day(rig, coin, 0.10),
        )


def test_rank_orders_by_predicted_profit(rig: Rig, coins: list[Coin]) -> None:
    optimizer = ProfitabilityOptimizer()
    ranked = optimizer.rank(rig, coins, 0.10)
    profits = [r.predicted_profit_per_day for r in ranked]
    assert profits == sorted(profits, reverse=True)


def test_best_is_first_of_rank(rig: Rig, coins: list[Coin]) -> None:
    optimizer = ProfitabilityOptimizer()
    assert optimizer.best(rig, coins, 0.10).symbol == optimizer.rank(
        rig, coins, 0.10
    )[0].symbol


def test_best_on_empty_raises(rig: Rig) -> None:
    with pytest.raises(ValueError):
        ProfitabilityOptimizer().best(rig, [], 0.10)


def test_fit_requires_matching_lengths(rig: Rig, coins: list[Coin]) -> None:
    optimizer = ProfitabilityOptimizer()
    with pytest.raises(ValueError):
        optimizer.fit([(rig, coins[0], 0.10)], [1.0, 2.0])


def test_fit_uses_trained_model(rig: Rig, coins: list[Coin]) -> None:
    # Generate enough varied samples to make the linear fit well-determined
    # (more samples than features) and train against a constant target so we
    # can verify the learned model is used in place of the analytic fallback.
    samples = [
        (
            Rig(
                hashrate_hs=rig.hashrate_hs * (1 + 0.1 * i),
                power_watts=rig.power_watts * (1 + 0.05 * i),
            ),
            coins[i % len(coins)],
            0.05 + 0.01 * i,
        )
        for i in range(20)
    ]
    constant_target = 42.0
    targets = [constant_target] * len(samples)
    optimizer = ProfitabilityOptimizer().fit(samples, targets)
    predicted = optimizer.predict(rig, coins[0], 0.10)
    analytic = expected_profit_per_day(rig, coins[0], 0.10)
    # Fitting to a constant target should drive the prediction near that
    # target and away from the analytic value.
    assert abs(predicted - constant_target) < abs(predicted - analytic)
