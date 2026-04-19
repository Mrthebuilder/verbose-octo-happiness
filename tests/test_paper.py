from __future__ import annotations

import io
import json
from pathlib import Path

from software.paper import (
    DEMO_INPUT,
    PAPER_BANNER,
    PAPER_FOOTER,
    format_report,
    load_input,
    main,
)


def test_demo_report_includes_every_section_and_disclaimer() -> None:
    report = format_report(DEMO_INPUT)
    # Banner + footer disclaimers always present.
    assert PAPER_BANNER in report
    assert PAPER_FOOTER in report
    assert "PAPER PROJECTION" in report
    assert "not a licensed broker" in report

    # Every section heading is rendered in the demo.
    for heading in (
        "Mining projection",
        "Holdings",
        "Staking (projected)",
        "Bonds (held to maturity)",
        "IPO allocations",
        "Portfolio summary (projected)",
    ):
        assert heading in report


def test_main_writes_demo_report_to_stdout() -> None:
    buf = io.StringIO()
    rc = main(["--demo"], out=buf)
    assert rc == 0
    assert "Brick paper-mode wealth projection" in buf.getvalue()
    assert "Portfolio summary (projected)" in buf.getvalue()


def test_load_input_roundtrips_from_json(tmp_path: Path) -> None:
    cfg = {
        "electricity_cost_per_kwh": 0.1,
        "rig": {"hashrate_hs": 1e10, "power_watts": 500},
        "coins": [
            {
                "symbol": "BTC",
                "price_usd": 60000,
                "network_hashrate_hs": 5e20,
                "block_reward": 3.125,
                "block_time_seconds": 600,
            }
        ],
        "holdings": [
            {
                "symbol": "ETH",
                "quantity": 1.0,
                "cost_basis_per_unit": 2000.0,
                "current_price_per_unit": 3000.0,
            }
        ],
        "staking": [
            {
                "symbol": "ETH",
                "quantity": 1.0,
                "apy": 0.04,
                "days": 365,
                "price_per_unit": 3000.0,
            }
        ],
        "bonds": [
            {
                "label": "1Y",
                "face_value": 1000.0,
                "coupon_rate_annual": 0.05,
                "years_to_maturity": 1.0,
                "price": 1000.0,
            }
        ],
        "ipos": [
            {
                "symbol": "EXAMPL",
                "shares_allocated": 10,
                "issue_price": 20,
                "current_price": 25,
            }
        ],
    }
    path = tmp_path / "wealth.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    inp = load_input(path)
    assert inp.electricity_cost_per_kwh == 0.1
    assert inp.rig is not None
    assert inp.rig.hashrate_hs == 1e10
    assert inp.coins[0].symbol == "BTC"
    assert inp.holdings[0].symbol == "ETH"
    assert inp.staking[0].apy == 0.04
    assert inp.bonds[0].face_value == 1000.0
    assert inp.ipos[0].shares_allocated == 10.0


def test_empty_sections_are_elided() -> None:
    from software.paper import PaperInput

    empty = PaperInput()
    report = format_report(empty)
    # Banner and footer still render, but none of the data sections
    # should appear.
    assert PAPER_BANNER in report
    assert PAPER_FOOTER in report
    for heading in (
        "Mining projection",
        "Holdings",
        "Staking (projected)",
        "Bonds (held to maturity)",
        "IPO allocations",
    ):
        assert heading not in report
    # Summary line is always shown even if every total is zero, so
    # the user sees an explicit "nothing projected" readout.
    assert "Portfolio summary (projected)" in report
