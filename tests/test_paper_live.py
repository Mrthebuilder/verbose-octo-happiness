"""CLI-level tests for the --live-btc path.

These tests patch ``software.wallet_live._http_get_json`` so nothing
actually hits the network, which keeps CI deterministic.
"""

from __future__ import annotations

import io

import pytest

from software import wallet_live
from software.paper import main

RESPONSES = {
    "https://mempool.space/api/address/1abc": {
        "chain_stats": {
            "funded_txo_sum": 50_000_000,
            "spent_txo_sum": 0,
        },
        "mempool_stats": {
            "funded_txo_sum": 0,
            "spent_txo_sum": 0,
        },
    },
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin&vs_currencies=usd": {"bitcoin": {"usd": 60000.0}},
}


def _stub_http_get_json(url: str) -> dict:
    return RESPONSES[url]


def test_live_btc_adds_holding_to_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wallet_live, "_http_get_json", _stub_http_get_json)
    out = io.StringIO()
    err = io.StringIO()
    rc = main(["--demo", "--live-btc", "1abc"], out=out, err=err)
    assert rc == 0
    report = out.getvalue()
    # 50_000_000 sats = 0.5 BTC @ $60k = $30,000.
    assert "BTC" in report
    # The holding-row width renders quantity with 4 decimals.
    assert "0.5000" in report
    # Live call succeeded so no warning should be printed.
    assert err.getvalue() == ""


def test_live_btc_only_with_no_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wallet_live, "_http_get_json", _stub_http_get_json)
    out = io.StringIO()
    err = io.StringIO()
    rc = main(["--live-btc", "1abc"], out=out, err=err)
    assert rc == 0
    report = out.getvalue()
    # No mining / staking / bond sections (they all live in --demo).
    assert "Mining projection" not in report
    assert "Staking (projected)" not in report
    # But holdings + summary should render the live BTC balance.
    assert "Holdings" in report
    assert "BTC" in report
    assert "Portfolio summary (projected)" in report


def test_live_btc_fetch_error_prints_warning_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_url: str) -> dict:
        raise wallet_live.LiveFetchError("network error: URLError")

    monkeypatch.setattr(wallet_live, "_http_get_json", boom)
    out = io.StringIO()
    err = io.StringIO()
    rc = main(["--demo", "--live-btc", "1dead"], out=out, err=err)
    assert rc == 0
    # The demo-mode base portfolio still renders.
    assert "Mining projection" in out.getvalue()
    # The live failure is announced on stderr so scripts can capture it.
    assert "could not fetch live balance" in err.getvalue()
    assert "1dead" in err.getvalue()


def test_main_errors_without_any_input_mode(capsys: pytest.CaptureFixture[str]) -> None:
    # argparse calls ``parser.error`` which exits with code 2.
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
