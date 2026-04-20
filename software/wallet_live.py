"""Optional live blockchain balance fetcher.

This module makes outbound HTTPS calls to public blockchain explorers
and price feeds. It is **off by default**. It only runs when a caller
explicitly invokes it (for example via the ``--live-btc`` flag on the
paper-mode CLI).

Why it is a separate module:

* ``software.wallet`` is pure and offline-testable. Mixing network I/O
  into it would make the paper-mode path implicitly dependent on
  public services being up.
* Brick's reference deployment is outbound-only to a pinned
  allowlist. The endpoints this module calls are exactly the kind of
  thing that belongs on that allowlist, not buried inside every
  function.

Endpoints used (public, no API keys, no user data sent):

* ``https://mempool.space/api/address/<addr>`` — public Bitcoin
  address stats. Nothing about the caller is disclosed except the
  address being queried and the caller's IP.
* ``https://ethereum-rpc.publicnode.com`` — public Ethereum JSON-RPC
  endpoint. We only call ``eth_getBalance``; no wallet, no nonce, no
  signed transaction is ever sent.
* ``https://api.coingecko.com/api/v3/simple/price`` — public USD
  prices. CoinGecko rate-limits unauthenticated callers.

This module never holds keys, never signs anything, and never
transmits anything the caller did not explicitly pass to it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .wallet import BalanceSnapshot, WalletAddress

SATS_PER_BTC = 100_000_000
WEI_PER_ETH = 10**18

JsonFetcher = Callable[[str], dict]
JsonPoster = Callable[[str, dict], dict]

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_USER_AGENT = "brick-paper/1.0 (+https://github.com/Mrthebuilder/verbose-octo-happiness)"
DEFAULT_ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"


class LiveFetchError(RuntimeError):
    """Raised when a live balance or price lookup fails.

    The error message is intentionally terse and never includes the
    full URL (which contains the queried address) so Brick's logs do
    not pick up public-but-linkable address metadata.
    """


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": DEFAULT_USER_AGENT}
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - explicit HTTPS only; urls below
            req, timeout=DEFAULT_TIMEOUT_SECONDS
        ) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LiveFetchError(f"network error: {exc.__class__.__name__}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LiveFetchError("response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LiveFetchError("response JSON was not an object")
    return parsed


def _http_post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - explicit HTTPS JSON-RPC
            req, timeout=DEFAULT_TIMEOUT_SECONDS
        ) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LiveFetchError(f"network error: {exc.__class__.__name__}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveFetchError("JSON-RPC response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LiveFetchError("JSON-RPC response was not an object")
    return parsed


def _default_fetcher() -> JsonFetcher:
    """Return the module-level HTTP GET fetcher at call time.

    Resolved lazily so tests can monkeypatch
    ``wallet_live._http_get_json`` and have every helper pick up the
    replacement without having to thread a ``fetcher`` kwarg through.
    """
    return _http_get_json


def _default_poster() -> JsonPoster:
    """Return the module-level HTTP POST fetcher at call time."""
    return _http_post_json


def fetch_btc_balance_sats(
    address: str, *, fetcher: JsonFetcher | None = None
) -> int:
    """Return a Bitcoin address's confirmed + mempool balance in satoshis.

    ``fetcher`` is injectable so tests never hit the network. When
    ``None``, the module-level :func:`_http_get_json` is used.
    """
    if not address:
        raise ValueError("address must be non-empty")
    fetcher = fetcher or _default_fetcher()
    url = f"https://mempool.space/api/address/{urllib.parse.quote(address, safe='')}"
    data = fetcher(url)
    try:
        chain = data.get("chain_stats") or {}
        mempool = data.get("mempool_stats") or {}
        funded = int(chain.get("funded_txo_sum", 0)) + int(
            mempool.get("funded_txo_sum", 0)
        )
        spent = int(chain.get("spent_txo_sum", 0)) + int(
            mempool.get("spent_txo_sum", 0)
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise LiveFetchError("unexpected response shape from explorer") from exc
    return max(funded - spent, 0)


def fetch_price_usd(
    coingecko_id: str, *, fetcher: JsonFetcher | None = None
) -> float:
    """Return the USD price of ``coingecko_id`` from CoinGecko."""
    if not coingecko_id:
        raise ValueError("coingecko_id must be non-empty")
    fetcher = fetcher or _default_fetcher()
    safe_id = urllib.parse.quote(coingecko_id, safe="")
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={safe_id}&vs_currencies=usd"
    )
    data = fetcher(url)
    try:
        return float(data[coingecko_id]["usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveFetchError(
            f"no USD price returned for {coingecko_id!r}"
        ) from exc


def fetch_eth_balance_wei(
    address: str,
    *,
    rpc_url: str = DEFAULT_ETH_RPC_URL,
    poster: JsonPoster | None = None,
) -> int:
    """Return the balance of ``address`` in wei via JSON-RPC ``eth_getBalance``.

    ``poster`` is injectable so tests never hit the network. When
    ``None``, the module-level :func:`_http_post_json` is used.
    """
    if not address:
        raise ValueError("address must be non-empty")
    poster = poster or _default_poster()
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1,
    }
    data = poster(rpc_url, payload)
    if "error" in data:
        err = data["error"]
        message = err.get("message", "unknown error") if isinstance(err, dict) else str(err)
        raise LiveFetchError(f"JSON-RPC error: {message}")
    try:
        result = data["result"]
        if not isinstance(result, str) or not result.startswith("0x"):
            raise LiveFetchError("unexpected eth_getBalance result shape")
        return int(result, 16)
    except (KeyError, TypeError, ValueError) as exc:
        raise LiveFetchError("unexpected eth_getBalance result shape") from exc


def live_eth_snapshot(
    label: str,
    address: str,
    *,
    rpc_url: str = DEFAULT_ETH_RPC_URL,
    poster: JsonPoster | None = None,
    fetcher: JsonFetcher | None = None,
) -> BalanceSnapshot:
    """Build a :class:`BalanceSnapshot` for an Ethereum address.

    Makes one JSON-RPC call to ``rpc_url`` for the balance and one
    HTTPS GET to CoinGecko for the USD price. Either call failing
    raises :class:`LiveFetchError`.
    """
    if not label:
        raise ValueError("label must be non-empty")
    if not address:
        raise ValueError("address must be non-empty")
    wei = fetch_eth_balance_wei(address, rpc_url=rpc_url, poster=poster)
    eth = wei / WEI_PER_ETH
    price = fetch_price_usd("ethereum", fetcher=fetcher)
    wallet_addr = WalletAddress(label=label, chain="ethereum", address=address)
    return BalanceSnapshot(
        address=wallet_addr,
        symbol="ETH",
        quantity=eth,
        price_usd=price,
    )


def live_btc_snapshot(
    label: str,
    address: str,
    *,
    fetcher: JsonFetcher | None = None,
) -> BalanceSnapshot:
    """Build a :class:`BalanceSnapshot` for a Bitcoin address.

    Makes two HTTPS calls: one to mempool.space for the balance, one
    to CoinGecko for the USD price. Either call failing raises
    :class:`LiveFetchError`; the caller is responsible for deciding
    whether to fall back to a user-supplied snapshot.
    """
    if not label:
        raise ValueError("label must be non-empty")
    if not address:
        raise ValueError("address must be non-empty")
    sats = fetch_btc_balance_sats(address, fetcher=fetcher)
    btc = sats / SATS_PER_BTC
    price = fetch_price_usd("bitcoin", fetcher=fetcher)
    wallet_addr = WalletAddress(label=label, chain="bitcoin", address=address)
    return BalanceSnapshot(
        address=wallet_addr,
        symbol="BTC",
        quantity=btc,
        price_usd=price,
    )


__all__ = [
    "DEFAULT_ETH_RPC_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "JsonFetcher",
    "JsonPoster",
    "LiveFetchError",
    "SATS_PER_BTC",
    "WEI_PER_ETH",
    "fetch_btc_balance_sats",
    "fetch_eth_balance_wei",
    "fetch_price_usd",
    "live_btc_snapshot",
    "live_eth_snapshot",
]
