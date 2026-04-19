"""Read-only wallet integration.

Brick never holds or handles private keys. If the user wants Brick to
show real balances, they provide **public addresses only** and Brick
renders those addresses + caller-supplied balances into the paper-mode
wealth view.

This module deliberately does not make any network calls. Fetching
balances from a blockchain is the caller's responsibility — typically
done in a separate process (or in the user's own wallet app such as
the Unstoppable Wallet iOS app) and passed in as a ``BalanceSnapshot``.

Why this split:

* Brick stays deterministic and offline-testable.
* Brick cannot accidentally leak anything sensitive — there is nothing
  sensitive in this module.
* The user can audit exactly which numbers Brick saw by looking at
  the balance snapshot they supplied.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .portfolio import CoinHolding

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_BTC_ADDRESS_RE = re.compile(
    r"^(bc1[a-zA-HJ-NP-Z0-9]{25,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$"
)


@dataclass(frozen=True)
class WalletAddress:
    """A labelled public address on a specific chain.

    Attributes:
        label: Human-readable name, e.g. ``"cold storage"``.
        chain: Lowercase chain identifier, e.g. ``"ethereum"``, ``"bitcoin"``.
        address: The public address string.
    """

    label: str
    chain: str
    address: str

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("label must be non-empty")
        if not self.chain:
            raise ValueError("chain must be non-empty")
        if not self.address:
            raise ValueError("address must be non-empty")


@dataclass(frozen=True)
class BalanceSnapshot:
    """A snapshot of one token balance at a public address.

    The caller is responsible for filling this in from whatever source
    they trust (their iOS wallet app, a block explorer, a local node).
    Brick uses the snapshot verbatim.

    Attributes:
        address: The :class:`WalletAddress` this balance is for.
        symbol: Token ticker, e.g. ``"ETH"`` or ``"USDC"``.
        quantity: Amount held in native units.
        price_usd: Caller-supplied USD price per unit.
        cost_basis_per_unit: Optional cost basis. Defaults to the
            current price, giving a zero unrealized P&L line for users
            who don't track cost basis in their wallet.
    """

    address: WalletAddress
    symbol: str
    quantity: float
    price_usd: float
    cost_basis_per_unit: float | None = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.price_usd < 0:
            raise ValueError("price_usd must be non-negative")
        if (
            self.cost_basis_per_unit is not None
            and self.cost_basis_per_unit < 0
        ):
            raise ValueError("cost_basis_per_unit must be non-negative")

    def to_holding(self) -> CoinHolding:
        """Convert this snapshot into a :class:`CoinHolding`.

        The holding uses ``cost_basis_per_unit`` if supplied, otherwise
        the current price (producing a zero unrealized P&L baseline).
        """
        basis = (
            self.cost_basis_per_unit
            if self.cost_basis_per_unit is not None
            else self.price_usd
        )
        return CoinHolding(
            symbol=self.symbol,
            quantity=self.quantity,
            cost_basis_per_unit=basis,
            current_price_per_unit=self.price_usd,
        )


def validate_address(address: WalletAddress) -> list[str]:
    """Return a list of validation problems (empty if the address is ok).

    This is a *syntactic* check: it verifies that ETH and BTC addresses
    look plausibly like ETH and BTC addresses. It does not contact any
    network.
    """
    problems: list[str] = []
    chain = address.chain.lower()
    if chain == "ethereum":
        if not _ETH_ADDRESS_RE.match(address.address):
            problems.append(
                f"address {address.address!r} does not look like a "
                "0x-prefixed 20-byte Ethereum address"
            )
    elif chain == "bitcoin":
        if not _BTC_ADDRESS_RE.match(address.address):
            problems.append(
                f"address {address.address!r} does not look like a "
                "mainnet Bitcoin address"
            )
    # Other chains: no syntactic check, trust the caller.
    return problems


def snapshots_to_holdings(
    snapshots: Iterable[BalanceSnapshot],
) -> tuple[CoinHolding, ...]:
    """Convert a sequence of balance snapshots into holdings."""
    return tuple(s.to_holding() for s in snapshots)


def load_snapshots(path: str | Path) -> tuple[BalanceSnapshot, ...]:
    """Load balance snapshots from a JSON file.

    The file layout is::

        [
          {
            "address": {"label": "cold", "chain": "ethereum",
                        "address": "0x..."},
            "symbol": "ETH",
            "quantity": 2.0,
            "price_usd": 3200.0,
            "cost_basis_per_unit": 2500.0
          },
          ...
        ]
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[BalanceSnapshot] = []
    for row in raw:
        addr_raw = row["address"]
        address = WalletAddress(
            label=str(addr_raw["label"]),
            chain=str(addr_raw["chain"]),
            address=str(addr_raw["address"]),
        )
        cost_basis = row.get("cost_basis_per_unit")
        out.append(
            BalanceSnapshot(
                address=address,
                symbol=str(row["symbol"]),
                quantity=float(row["quantity"]),
                price_usd=float(row["price_usd"]),
                cost_basis_per_unit=(
                    None if cost_basis is None else float(cost_basis)
                ),
            )
        )
    return tuple(out)


__all__ = [
    "BalanceSnapshot",
    "WalletAddress",
    "load_snapshots",
    "snapshots_to_holdings",
    "validate_address",
]
