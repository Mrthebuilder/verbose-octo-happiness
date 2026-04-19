"""Standalone mining simulation, backed by :mod:`software.profitability`.

Historically this file produced random numbers in a loop. It now drives
the simulation from realistic inputs (hashrate, power, coin parameters,
electricity cost) so the results line up with the profitability
calculator used elsewhere in the project.
"""

from __future__ import annotations

import logging
import time

from software.profitability import (
    Coin,
    Rig,
    electricity_cost_per_day,
    expected_coins_per_day,
    expected_profit_per_day,
    expected_revenue_per_day,
)

logger = logging.getLogger(__name__)

DEFAULT_TICK_SECONDS = 10


class CryptoMiner:
    """Simulate a rig mining a single coin at its analytic expected rate."""

    def __init__(
        self,
        rig: Rig,
        coin: Coin,
        electricity_cost_per_kwh: float,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")
        self.rig = rig
        self.coin = coin
        self.electricity_cost_per_kwh = electricity_cost_per_kwh
        self.tick_seconds = tick_seconds
        self.mining = False
        self.total_coins_mined = 0.0
        self.total_profit_usd = 0.0

    def mine_tick(self) -> tuple[float, float]:
        """Advance the simulation by one tick.

        Returns the tuple ``(coins_mined_this_tick, profit_usd_this_tick)``.
        """
        day_fraction = self.tick_seconds / 86_400
        coins = expected_coins_per_day(self.rig, self.coin) * day_fraction
        profit = (
            expected_profit_per_day(
                self.rig, self.coin, self.electricity_cost_per_kwh
            )
            * day_fraction
        )
        self.total_coins_mined += coins
        self.total_profit_usd += profit
        return coins, profit

    def start(self) -> None:
        """Run the simulation loop until :meth:`stop` is called."""
        logger.info(
            "Starting mining: rig=%s coin=%s daily_revenue=$%.4f electricity=$%.4f",
            self.rig,
            self.coin.symbol,
            expected_revenue_per_day(self.rig, self.coin),
            electricity_cost_per_day(self.rig, self.electricity_cost_per_kwh),
        )
        self.mining = True
        try:
            while self.mining:
                coins, profit = self.mine_tick()
                logger.info(
                    "Mined %.8f %s (+$%.4f). Totals: %.8f %s, $%.4f profit",
                    coins,
                    self.coin.symbol,
                    profit,
                    self.total_coins_mined,
                    self.coin.symbol,
                    self.total_profit_usd,
                )
                time.sleep(self.tick_seconds)
        finally:
            self.mining = False

    def stop(self) -> None:
        """Signal the simulation loop to exit on the next tick."""
        logger.info("Stopping mining.")
        self.mining = False


def _demo_miner() -> CryptoMiner:
    """Build a demo miner with reasonable defaults for a BTC-like coin."""
    rig = Rig(hashrate_hs=100e12, power_watts=3250)
    coin = Coin(
        symbol="BTC",
        price_usd=60_000.0,
        network_hashrate_hs=500e18,
        block_reward=3.125,
        block_time_seconds=600.0,
    )
    return CryptoMiner(rig=rig, coin=coin, electricity_cost_per_kwh=0.10)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    miner = _demo_miner()
    try:
        miner.start()
    except KeyboardInterrupt:
        miner.stop()
