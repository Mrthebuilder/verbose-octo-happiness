from __future__ import annotations

import math

import pytest

from software.profitability import (
    Coin,
    Rig,
    break_even_price,
    electricity_cost_per_day,
    expected_coins_per_day,
    expected_profit_per_day,
    expected_revenue_per_day,
)


@pytest.fixture
def rig() -> Rig:
    return Rig(hashrate_hs=100e12, power_watts=3250)


@pytest.fixture
def coin() -> Coin:
    return Coin(
        symbol="BTC",
        price_usd=60_000.0,
        network_hashrate_hs=500e18,
        block_reward=3.125,
        block_time_seconds=600.0,
    )


def test_expected_coins_per_day_matches_formula(rig: Rig, coin: Coin) -> None:
    expected = (
        (rig.hashrate_hs / coin.network_hashrate_hs)
        * (86_400 / coin.block_time_seconds)
        * coin.block_reward
    )
    assert math.isclose(expected_coins_per_day(rig, coin), expected, rel_tol=1e-12)


def test_expected_revenue_scales_with_price(rig: Rig, coin: Coin) -> None:
    base = expected_revenue_per_day(rig, coin)
    doubled = Coin(**{**coin.__dict__, "price_usd": coin.price_usd * 2})
    assert math.isclose(expected_revenue_per_day(rig, doubled), 2 * base)


def test_electricity_cost_per_day_known_value() -> None:
    rig = Rig(hashrate_hs=0, power_watts=1000)
    # 1000W * 24h = 24 kWh/day. At $0.10/kWh = $2.40/day.
    assert math.isclose(electricity_cost_per_day(rig, 0.10), 2.40)


def test_expected_profit_is_revenue_minus_electricity(
    rig: Rig, coin: Coin
) -> None:
    cost = 0.07
    assert math.isclose(
        expected_profit_per_day(rig, coin, cost),
        expected_revenue_per_day(rig, coin) - electricity_cost_per_day(rig, cost),
    )


def test_break_even_price_covers_electricity(rig: Rig, coin: Coin) -> None:
    cost = 0.08
    price = break_even_price(rig, coin, cost)
    at_break_even = Coin(**{**coin.__dict__, "price_usd": price})
    assert math.isclose(
        expected_profit_per_day(rig, at_break_even, cost), 0.0, abs_tol=1e-6
    )


def test_zero_hashrate_rig_cannot_break_even(coin: Coin) -> None:
    zero_rig = Rig(hashrate_hs=0, power_watts=1000)
    with pytest.raises(ValueError):
        break_even_price(zero_rig, coin, 0.10)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"hashrate_hs": -1, "power_watts": 100},
        {"hashrate_hs": 1, "power_watts": -100},
    ],
)
def test_rig_rejects_negative_values(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Rig(**kwargs)


@pytest.mark.parametrize(
    "override",
    [
        {"price_usd": -1},
        {"network_hashrate_hs": 0},
        {"block_reward": -1},
        {"block_time_seconds": 0},
    ],
)
def test_coin_rejects_invalid_values(coin: Coin, override: dict) -> None:
    kwargs = {**coin.__dict__, **override}
    with pytest.raises(ValueError):
        Coin(**kwargs)
