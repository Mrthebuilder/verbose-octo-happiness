"""Pure-math profitability calculations for a mining rig.

These helpers intentionally take no external dependencies and no I/O so
they can be used as the ground truth for simulations, the optimizer, and
the LLM assistant's tool calls.

All monetary values are in USD and all time bases are per-day unless
noted otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class Rig:
    """A mining rig's physical characteristics.

    Attributes:
        hashrate_hs: Hashrate in hashes per second.
        power_watts: Power draw in watts at the wall.
    """

    hashrate_hs: float
    power_watts: float

    def __post_init__(self) -> None:
        if self.hashrate_hs < 0:
            raise ValueError("hashrate_hs must be non-negative")
        if self.power_watts < 0:
            raise ValueError("power_watts must be non-negative")


@dataclass(frozen=True)
class Coin:
    """Network-level parameters for a proof-of-work coin.

    Attributes:
        symbol: Ticker symbol, e.g. "BTC".
        price_usd: Spot price per coin in USD.
        network_hashrate_hs: Total network hashrate in hashes per second.
        block_reward: Coins awarded per block (subsidy + average fees).
        block_time_seconds: Average seconds between blocks.
    """

    symbol: str
    price_usd: float
    network_hashrate_hs: float
    block_reward: float
    block_time_seconds: float

    def __post_init__(self) -> None:
        if self.price_usd < 0:
            raise ValueError("price_usd must be non-negative")
        if self.network_hashrate_hs <= 0:
            raise ValueError("network_hashrate_hs must be positive")
        if self.block_reward < 0:
            raise ValueError("block_reward must be non-negative")
        if self.block_time_seconds <= 0:
            raise ValueError("block_time_seconds must be positive")


def expected_coins_per_day(rig: Rig, coin: Coin) -> float:
    """Expected coins mined per day at the rig's share of network hashrate."""
    share = rig.hashrate_hs / coin.network_hashrate_hs
    blocks_per_day = SECONDS_PER_DAY / coin.block_time_seconds
    return share * blocks_per_day * coin.block_reward


def expected_revenue_per_day(rig: Rig, coin: Coin) -> float:
    """Expected gross revenue in USD per day before electricity."""
    return expected_coins_per_day(rig, coin) * coin.price_usd


def electricity_cost_per_day(rig: Rig, electricity_cost_per_kwh: float) -> float:
    """Electricity cost in USD per day for continuous operation."""
    if electricity_cost_per_kwh < 0:
        raise ValueError("electricity_cost_per_kwh must be non-negative")
    kwh_per_day = rig.power_watts * 24 / 1000
    return kwh_per_day * electricity_cost_per_kwh


def expected_profit_per_day(
    rig: Rig,
    coin: Coin,
    electricity_cost_per_kwh: float,
) -> float:
    """Expected net profit in USD per day (revenue minus electricity)."""
    return expected_revenue_per_day(rig, coin) - electricity_cost_per_day(
        rig, electricity_cost_per_kwh
    )


def break_even_price(
    rig: Rig,
    coin: Coin,
    electricity_cost_per_kwh: float,
) -> float:
    """Coin price at which daily revenue exactly covers electricity."""
    coins = expected_coins_per_day(rig, coin)
    if coins == 0:
        raise ValueError("rig cannot mine this coin (zero expected coins/day)")
    return electricity_cost_per_day(rig, electricity_cost_per_kwh) / coins
