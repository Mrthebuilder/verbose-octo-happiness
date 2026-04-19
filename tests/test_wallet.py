from __future__ import annotations

import json
from pathlib import Path

import pytest

from software.wallet import (
    BalanceSnapshot,
    WalletAddress,
    load_snapshots,
    snapshots_to_holdings,
    validate_address,
)


def test_wallet_address_requires_non_empty_fields() -> None:
    with pytest.raises(ValueError):
        WalletAddress(label="", chain="ethereum", address="0x" + "a" * 40)
    with pytest.raises(ValueError):
        WalletAddress(label="cold", chain="", address="0x" + "a" * 40)
    with pytest.raises(ValueError):
        WalletAddress(label="cold", chain="ethereum", address="")


def test_validate_address_ethereum() -> None:
    good = WalletAddress(
        label="cold",
        chain="ethereum",
        address="0x" + "a" * 40,
    )
    assert validate_address(good) == []

    bad = WalletAddress(
        label="cold",
        chain="ethereum",
        address="not-an-address",
    )
    problems = validate_address(bad)
    assert problems and "Ethereum" in problems[0]


def test_validate_address_bitcoin() -> None:
    # A representative mainnet bech32 address (not a real wallet).
    good = WalletAddress(
        label="cold",
        chain="bitcoin",
        address="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
    )
    assert validate_address(good) == []

    bad = WalletAddress(
        label="cold",
        chain="bitcoin",
        address="not-an-address",
    )
    problems = validate_address(bad)
    assert problems and "Bitcoin" in problems[0]


def test_validate_unknown_chain_trusts_caller() -> None:
    # We do not ship syntactic validators for every chain; unknown
    # chains are accepted so users can bring their own.
    addr = WalletAddress(
        label="solana-main",
        chain="solana",
        address="SoMeSoLanAaDdRess11111111111111111111111111",
    )
    assert validate_address(addr) == []


def test_snapshot_to_holding_uses_cost_basis() -> None:
    addr = WalletAddress(
        label="cold",
        chain="ethereum",
        address="0x" + "a" * 40,
    )
    snap = BalanceSnapshot(
        address=addr,
        symbol="ETH",
        quantity=2.0,
        price_usd=3200.0,
        cost_basis_per_unit=2500.0,
    )
    holding = snap.to_holding()
    assert holding.symbol == "ETH"
    assert holding.quantity == 2.0
    assert holding.cost_basis_per_unit == 2500.0
    assert holding.current_price_per_unit == 3200.0
    assert holding.unrealized_pnl == pytest.approx(1400.0)


def test_snapshot_to_holding_defaults_cost_basis_to_current_price() -> None:
    addr = WalletAddress(
        label="cold",
        chain="ethereum",
        address="0x" + "a" * 40,
    )
    snap = BalanceSnapshot(
        address=addr,
        symbol="ETH",
        quantity=2.0,
        price_usd=3200.0,
        cost_basis_per_unit=None,
    )
    holding = snap.to_holding()
    assert holding.cost_basis_per_unit == 3200.0
    assert holding.unrealized_pnl == pytest.approx(0.0)


def test_snapshots_to_holdings_preserves_order() -> None:
    addr = WalletAddress(
        label="cold",
        chain="ethereum",
        address="0x" + "a" * 40,
    )
    snaps = [
        BalanceSnapshot(address=addr, symbol="ETH", quantity=1.0, price_usd=3000.0),
        BalanceSnapshot(address=addr, symbol="USDC", quantity=500.0, price_usd=1.0),
    ]
    holdings = snapshots_to_holdings(snaps)
    assert [h.symbol for h in holdings] == ["ETH", "USDC"]


def test_load_snapshots_from_json(tmp_path: Path) -> None:
    raw = [
        {
            "address": {
                "label": "cold",
                "chain": "ethereum",
                "address": "0x" + "a" * 40,
            },
            "symbol": "ETH",
            "quantity": 2.0,
            "price_usd": 3200.0,
            "cost_basis_per_unit": 2500.0,
        },
        {
            "address": {
                "label": "btc-cold",
                "chain": "bitcoin",
                "address": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            },
            "symbol": "BTC",
            "quantity": 0.5,
            "price_usd": 65000.0,
        },
    ]
    path = tmp_path / "balances.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    snaps = load_snapshots(path)
    assert len(snaps) == 2
    assert snaps[0].address.chain == "ethereum"
    assert snaps[1].cost_basis_per_unit is None


def test_balance_snapshot_rejects_negatives() -> None:
    addr = WalletAddress(
        label="cold",
        chain="ethereum",
        address="0x" + "a" * 40,
    )
    with pytest.raises(ValueError):
        BalanceSnapshot(address=addr, symbol="ETH", quantity=-1.0, price_usd=100.0)
    with pytest.raises(ValueError):
        BalanceSnapshot(address=addr, symbol="ETH", quantity=1.0, price_usd=-1.0)
    with pytest.raises(ValueError):
        BalanceSnapshot(address=addr, symbol="", quantity=1.0, price_usd=100.0)
