from __future__ import annotations

import pytest

from software.wallet_live import (
    WEI_PER_ETH,
    LiveFetchError,
    fetch_btc_balance_sats,
    fetch_eth_balance_wei,
    fetch_price_usd,
    live_btc_snapshot,
    live_eth_snapshot,
)


def test_fetch_btc_balance_sums_confirmed_and_mempool() -> None:
    responses = {
        "https://mempool.space/api/address/1abc": {
            "chain_stats": {
                "funded_txo_sum": 100_000,
                "spent_txo_sum": 40_000,
            },
            "mempool_stats": {
                "funded_txo_sum": 5_000,
                "spent_txo_sum": 1_000,
            },
        },
    }
    sats = fetch_btc_balance_sats(
        "1abc", fetcher=lambda url: responses[url]
    )
    # 100k + 5k funded - 40k - 1k spent = 64_000 sats.
    assert sats == 64_000


def test_fetch_btc_balance_never_negative() -> None:
    # A newly-seen address with everything "spent" (e.g. double-spent
    # mempool weirdness) should still return a non-negative balance.
    data = {
        "chain_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0},
        "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 500},
    }
    sats = fetch_btc_balance_sats("1abc", fetcher=lambda _: data)
    assert sats == 0


def test_fetch_btc_balance_raises_on_malformed_response() -> None:
    with pytest.raises(LiveFetchError):
        fetch_btc_balance_sats(
            "1abc",
            fetcher=lambda _: {"chain_stats": "not a dict"},
        )


def test_fetch_btc_balance_requires_address() -> None:
    with pytest.raises(ValueError):
        fetch_btc_balance_sats("", fetcher=lambda _: {})


def test_fetch_price_usd_extracts_float() -> None:
    price = fetch_price_usd(
        "bitcoin",
        fetcher=lambda url: {"bitcoin": {"usd": 65000.5}}
        if "bitcoin" in url
        else {},
    )
    assert price == pytest.approx(65000.5)


def test_fetch_price_usd_raises_when_missing() -> None:
    with pytest.raises(LiveFetchError):
        fetch_price_usd(
            "bitcoin",
            fetcher=lambda _: {"not-bitcoin": {"usd": 100.0}},
        )


def test_live_btc_snapshot_builds_a_balance_snapshot() -> None:
    responses = {
        "https://mempool.space/api/address/1abc": {
            "chain_stats": {
                "funded_txo_sum": 200_000_000,
                "spent_txo_sum": 100_000_000,
            },
            "mempool_stats": {
                "funded_txo_sum": 0,
                "spent_txo_sum": 0,
            },
        },
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd": {"bitcoin": {"usd": 65000.0}},
    }
    snap = live_btc_snapshot(
        "cold", "1abc", fetcher=lambda url: responses[url]
    )
    # 100_000_000 sats = 1 BTC.
    assert snap.symbol == "BTC"
    assert snap.quantity == pytest.approx(1.0)
    assert snap.price_usd == pytest.approx(65000.0)
    assert snap.address.label == "cold"
    assert snap.address.chain == "bitcoin"


def test_live_btc_snapshot_rejects_empty_label() -> None:
    with pytest.raises(ValueError):
        live_btc_snapshot("", "1abc", fetcher=lambda _: {})


def test_fetch_eth_balance_decodes_hex_result() -> None:
    def poster(_url: str, _payload: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "result": "0xde0b6b3a7640000"}

    wei = fetch_eth_balance_wei("0xabc", poster=poster)
    # 0xde0b6b3a7640000 == 10**18 wei == 1 ETH.
    assert wei == WEI_PER_ETH


def test_fetch_eth_balance_raises_on_rpc_error() -> None:
    def poster(_url: str, _payload: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "boom"}}

    with pytest.raises(LiveFetchError, match="boom"):
        fetch_eth_balance_wei("0xabc", poster=poster)


def test_fetch_eth_balance_raises_on_bad_result_shape() -> None:
    def poster(_url: str, _payload: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "result": 12345}

    with pytest.raises(LiveFetchError):
        fetch_eth_balance_wei("0xabc", poster=poster)


def test_fetch_eth_balance_requires_address() -> None:
    with pytest.raises(ValueError):
        fetch_eth_balance_wei("", poster=lambda *_a: {})


def test_live_eth_snapshot_builds_a_balance_snapshot() -> None:
    # 2 ETH == 2 * 10**18 wei == 0x1bc16d674ec80000.
    two_eth_hex = hex(2 * WEI_PER_ETH)

    def poster(_url: str, _payload: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "result": two_eth_hex}

    def fetcher(url: str) -> dict:
        assert "ethereum" in url
        return {"ethereum": {"usd": 3000.0}}

    snap = live_eth_snapshot("hot", "0xabc", poster=poster, fetcher=fetcher)
    assert snap.symbol == "ETH"
    assert snap.quantity == pytest.approx(2.0)
    assert snap.price_usd == pytest.approx(3000.0)
    assert snap.address.chain == "ethereum"


def test_live_eth_snapshot_rejects_empty_label() -> None:
    with pytest.raises(ValueError):
        live_eth_snapshot(
            "", "0xabc", poster=lambda *_a: {}, fetcher=lambda _u: {}
        )
