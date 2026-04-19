"""Paper-mode wealth projection CLI.

This module lets a user see a unified projected P&L across:

* mining revenue from a rig they own (or plan to own),
* long positions in coins or stocks,
* staking yield on coins they intend to stake,
* Treasury bonds held to maturity,
* IPO allocations,

without connecting a wallet, depositing funds, or running any trading
or staking service. It only needs the user-supplied numbers.

**Paper mode makes no trades, holds no funds, and transmits no orders
to any exchange or broker.** If a user wants to actually invest, they
must do that themselves through a licensed broker or exchange.

Usage::

    python -m software.paper --demo
    python -m software.paper --config path/to/wealth.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .optimizer import ProfitabilityOptimizer
from .portfolio import (
    Bond,
    CoinHolding,
    IPOAllocation,
    PortfolioSummary,
    StakingPosition,
    summarize_portfolio,
)
from .profitability import (
    Coin,
    Rig,
    break_even_price,
    expected_coins_per_day,
    expected_profit_per_day,
    expected_revenue_per_day,
)


@dataclass(frozen=True)
class PaperInput:
    """Parsed inputs for a full paper-mode wealth run.

    Any of these sections may be empty; the report elides sections with
    no data.
    """

    rig: Rig | None = None
    coins: tuple[Coin, ...] = ()
    electricity_cost_per_kwh: float = 0.0
    holdings: tuple[CoinHolding, ...] = ()
    staking: tuple[StakingPosition, ...] = ()
    bonds: tuple[Bond, ...] = ()
    ipos: tuple[IPOAllocation, ...] = ()


DEMO_INPUT = PaperInput(
    rig=Rig(hashrate_hs=1.0e11, power_watts=3000.0),
    coins=(
        Coin(
            symbol="BTC",
            price_usd=65_000.0,
            network_hashrate_hs=5.0e20,
            block_reward=3.125,
            block_time_seconds=600.0,
        ),
        Coin(
            symbol="KAS",
            price_usd=0.12,
            network_hashrate_hs=1.0e15,
            block_reward=80.0,
            block_time_seconds=1.0,
        ),
    ),
    electricity_cost_per_kwh=0.12,
    holdings=(
        CoinHolding(
            symbol="ETH",
            quantity=2.0,
            cost_basis_per_unit=2_500.0,
            current_price_per_unit=3_200.0,
        ),
        CoinHolding(
            symbol="AAPL",
            quantity=10.0,
            cost_basis_per_unit=180.0,
            current_price_per_unit=195.0,
        ),
    ),
    staking=(
        StakingPosition(
            symbol="ETH",
            quantity=2.0,
            apy=0.04,
            days=365.0,
            price_per_unit=3_200.0,
        ),
    ),
    bonds=(
        Bond(
            label="10Y UST",
            face_value=10_000.0,
            coupon_rate_annual=0.045,
            years_to_maturity=10.0,
            price=9_800.0,
        ),
    ),
    ipos=(
        IPOAllocation(
            symbol="EXAMPL",
            shares_allocated=100.0,
            issue_price=20.0,
            current_price=24.0,
            lockup_days_remaining=0.0,
        ),
    ),
)


def load_input(path: str | Path) -> PaperInput:
    """Load a :class:`PaperInput` from a JSON config file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rig: Rig | None = None
    if "rig" in raw and raw["rig"] is not None:
        rig_raw = raw["rig"]
        rig = Rig(
            hashrate_hs=float(rig_raw["hashrate_hs"]),
            power_watts=float(rig_raw["power_watts"]),
        )
    coins = tuple(
        Coin(
            symbol=str(c["symbol"]),
            price_usd=float(c["price_usd"]),
            network_hashrate_hs=float(c["network_hashrate_hs"]),
            block_reward=float(c["block_reward"]),
            block_time_seconds=float(c["block_time_seconds"]),
        )
        for c in raw.get("coins", [])
    )
    holdings = tuple(
        CoinHolding(
            symbol=str(h["symbol"]),
            quantity=float(h["quantity"]),
            cost_basis_per_unit=float(h["cost_basis_per_unit"]),
            current_price_per_unit=float(h["current_price_per_unit"]),
        )
        for h in raw.get("holdings", [])
    )
    staking = tuple(
        StakingPosition(
            symbol=str(s["symbol"]),
            quantity=float(s["quantity"]),
            apy=float(s["apy"]),
            days=float(s["days"]),
            price_per_unit=float(s["price_per_unit"]),
        )
        for s in raw.get("staking", [])
    )
    bonds = tuple(
        Bond(
            label=str(b["label"]),
            face_value=float(b["face_value"]),
            coupon_rate_annual=float(b["coupon_rate_annual"]),
            years_to_maturity=float(b["years_to_maturity"]),
            price=float(b["price"]),
        )
        for b in raw.get("bonds", [])
    )
    ipos = tuple(
        IPOAllocation(
            symbol=str(i["symbol"]),
            shares_allocated=float(i["shares_allocated"]),
            issue_price=float(i["issue_price"]),
            current_price=float(i["current_price"]),
            lockup_days_remaining=float(i.get("lockup_days_remaining", 0.0)),
        )
        for i in raw.get("ipos", [])
    )
    return PaperInput(
        rig=rig,
        coins=coins,
        electricity_cost_per_kwh=float(raw.get("electricity_cost_per_kwh", 0.0)),
        holdings=holdings,
        staking=staking,
        bonds=bonds,
        ipos=ipos,
    )


PAPER_BANNER = (
    "Brick paper-mode wealth projection\n"
    "========================================\n"
    "PAPER PROJECTION -- no wallet is connected, no funds are deposited,\n"
    "no trades are placed. These numbers are computed entirely from\n"
    "values you supplied. Verify independently before acting."
)

PAPER_FOOTER = (
    "Brick does not move money. Every number above is a projection\n"
    "based on inputs you supplied. Brick is not a licensed broker,\n"
    "not a money transmitter, and not a financial advisor."
)


def _format_mining_section(inp: PaperInput) -> list[str]:
    if inp.rig is None or not inp.coins:
        return []
    optimizer = ProfitabilityOptimizer()
    rankings = optimizer.rank(inp.rig, inp.coins, inp.electricity_cost_per_kwh)
    lines: list[str] = []
    lines.append("Mining projection")
    lines.append("-" * 40)
    lines.append(
        f"Rig: {inp.rig.hashrate_hs:.3e} H/s @ {inp.rig.power_watts:.0f} W"
    )
    lines.append(
        f"Electricity: ${inp.electricity_cost_per_kwh:.3f} / kWh"
    )
    lines.append("")
    lines.append(
        f"{'Coin':<8}{'Coins/day':>14}{'Revenue/day':>14}"
        f"{'Profit/day':>14}{'Break-even $':>16}"
    )
    lines.append("-" * 66)
    for ranking in rankings:
        coin = ranking.coin
        coins = expected_coins_per_day(inp.rig, coin)
        revenue = expected_revenue_per_day(inp.rig, coin)
        profit = expected_profit_per_day(
            inp.rig, coin, inp.electricity_cost_per_kwh
        )
        try:
            be_price = break_even_price(
                inp.rig, coin, inp.electricity_cost_per_kwh
            )
            be_str = f"${be_price:.6f}"
        except ValueError:
            be_str = "n/a"
        lines.append(
            f"{coin.symbol:<8}"
            f"{coins:>14.6f}"
            f"{revenue:>13.2f} "
            f"{profit:>13.2f} "
            f"{be_str:>15}"
        )
    lines.append("")
    return lines


def _format_holdings_section(inp: PaperInput) -> list[str]:
    if not inp.holdings:
        return []
    lines: list[str] = []
    lines.append("Holdings")
    lines.append("-" * 40)
    lines.append(
        f"{'Symbol':<10}{'Qty':>10}{'Cost basis':>14}"
        f"{'Market value':>16}{'Unrealized':>14}"
    )
    for h in inp.holdings:
        lines.append(
            f"{h.symbol:<10}"
            f"{h.quantity:>10.4f}"
            f"{h.cost_basis:>14.2f}"
            f"{h.market_value:>16.2f}"
            f"{h.unrealized_pnl:>+14.2f}"
        )
    lines.append("")
    return lines


def _format_staking_section(inp: PaperInput) -> list[str]:
    if not inp.staking:
        return []
    lines: list[str] = []
    lines.append("Staking (projected)")
    lines.append("-" * 40)
    lines.append(
        f"{'Symbol':<10}{'Qty':>10}{'APY':>8}"
        f"{'Days':>8}{'Yield (units)':>16}{'Yield ($)':>14}"
    )
    for s in inp.staking:
        lines.append(
            f"{s.symbol:<10}"
            f"{s.quantity:>10.4f}"
            f"{s.apy * 100:>7.2f}%"
            f"{s.days:>8.0f}"
            f"{s.projected_yield_units:>16.6f}"
            f"{s.projected_yield_usd:>14.2f}"
        )
    lines.append("")
    return lines


def _format_bonds_section(inp: PaperInput) -> list[str]:
    if not inp.bonds:
        return []
    lines: list[str] = []
    lines.append("Bonds (held to maturity)")
    lines.append("-" * 40)
    lines.append(
        f"{'Label':<12}{'Face':>10}{'Coupon':>8}"
        f"{'Years':>7}{'Price':>10}{'Total return':>16}"
    )
    for b in inp.bonds:
        lines.append(
            f"{b.label:<12}"
            f"{b.face_value:>10.2f}"
            f"{b.coupon_rate_annual * 100:>7.2f}%"
            f"{b.years_to_maturity:>7.1f}"
            f"{b.price:>10.2f}"
            f"{b.projected_total_return:>+16.2f}"
        )
    lines.append("")
    return lines


def _format_ipo_section(inp: PaperInput) -> list[str]:
    if not inp.ipos:
        return []
    lines: list[str] = []
    lines.append("IPO allocations")
    lines.append("-" * 40)
    lines.append(
        f"{'Symbol':<10}{'Shares':>10}{'Issue $':>10}"
        f"{'Current $':>12}{'Lockup':>10}{'Unrealized':>14}"
    )
    for i in inp.ipos:
        lockup = (
            f"{int(i.lockup_days_remaining)}d"
            if i.locked
            else "unlocked"
        )
        lines.append(
            f"{i.symbol:<10}"
            f"{i.shares_allocated:>10.2f}"
            f"{i.issue_price:>10.2f}"
            f"{i.current_price:>12.2f}"
            f"{lockup:>10}"
            f"{i.unrealized_pnl:>+14.2f}"
        )
    lines.append("")
    return lines


def _format_summary_section(summary: PortfolioSummary) -> list[str]:
    lines: list[str] = []
    lines.append("Portfolio summary (projected)")
    lines.append("-" * 40)
    lines.append(
        f"Total cost basis:        ${summary.total_cost_basis:>14,.2f}"
    )
    lines.append(
        f"Total market value:      ${summary.total_market_value:>14,.2f}"
    )
    lines.append(
        f"Unrealized P&L:          ${summary.total_unrealized_pnl:>+14,.2f}"
    )
    lines.append(
        f"Projected staking yield: ${summary.projected_staking_yield:>+14,.2f}"
    )
    lines.append(
        f"Projected bond return:   ${summary.projected_bond_return:>+14,.2f}"
    )
    lines.append(
        f"Projected total return:  ${summary.projected_total_return:>+14,.2f}"
    )
    lines.append("")
    return lines


def format_report(inp: PaperInput) -> str:
    """Render a human-readable, deterministic wealth report."""
    out_lines: list[str] = [PAPER_BANNER, ""]
    for section in (
        _format_mining_section(inp),
        _format_holdings_section(inp),
        _format_staking_section(inp),
        _format_bonds_section(inp),
        _format_ipo_section(inp),
    ):
        out_lines.extend(section)
    summary = summarize_portfolio(
        holdings=inp.holdings,
        staking=inp.staking,
        bonds=inp.bonds,
        ipos=inp.ipos,
    )
    out_lines.extend(_format_summary_section(summary))
    out_lines.append(PAPER_FOOTER)
    return "\n".join(out_lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m software.paper",
        description=(
            "Paper-mode wealth projection: mining revenue plus coin, "
            "staking, bond, and IPO projections. No wallet, no funds, "
            "no trades."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--demo",
        action="store_true",
        help="Run with a built-in demo rig, coin, and portfolio slate.",
    )
    group.add_argument(
        "--config",
        type=str,
        help="Path to a JSON config file describing the full paper portfolio.",
    )
    return parser


def main(
    argv: list[str] | None = None, out: TextIO | None = None
) -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.demo:
        inp = DEMO_INPUT
    else:
        inp = load_input(args.config)
    report = format_report(inp)
    (out or sys.stdout).write(report)
    return 0


__all__ = [
    "DEMO_INPUT",
    "PAPER_BANNER",
    "PAPER_FOOTER",
    "PaperInput",
    "format_report",
    "load_input",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
