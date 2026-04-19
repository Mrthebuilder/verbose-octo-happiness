"""Paper-only portfolio projections.

This module models a user's *hypothetical* holdings across several
asset classes so Brick can show a unified projected P&L without ever
touching real money, a wallet, or a brokerage account. Every function
here is pure math on user-supplied numbers.

Explicit non-goals:

* This module does **not** execute trades.
* This module does **not** hold keys, addresses, or credentials.
* This module does **not** fetch prices from any exchange or
  brokerage. The caller supplies current prices.

If a caller ever wants to execute real trades, they must do so
through a licensed broker's API using the user's own account, with an
explicit per-trade confirmation. That path is out of scope for this
file on purpose.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


def _require_non_negative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class CoinHolding:
    """A long position in a coin, token, or stock.

    Attributes:
        symbol: Ticker, e.g. ``"ETH"`` or ``"AAPL"``.
        quantity: Number of units held.
        cost_basis_per_unit: What the user paid per unit (for P&L).
        current_price_per_unit: Caller-supplied spot price.
    """

    symbol: str
    quantity: float
    cost_basis_per_unit: float
    current_price_per_unit: float

    def __post_init__(self) -> None:
        _require_non_negative(self.quantity, "quantity")
        _require_non_negative(self.cost_basis_per_unit, "cost_basis_per_unit")
        _require_non_negative(
            self.current_price_per_unit, "current_price_per_unit"
        )

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.cost_basis_per_unit

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price_per_unit

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis


@dataclass(frozen=True)
class StakingPosition:
    """A hypothetical staking position.

    Attributes:
        symbol: Ticker of the staked coin.
        quantity: Amount staked.
        apy: Annual yield expressed as a decimal (``0.05`` = 5%).
        days: How many days the position is held.
        price_per_unit: Caller-supplied spot price used for USD
            conversion of the yield.
    """

    symbol: str
    quantity: float
    apy: float
    days: float
    price_per_unit: float

    def __post_init__(self) -> None:
        _require_non_negative(self.quantity, "quantity")
        _require_non_negative(self.apy, "apy")
        _require_non_negative(self.days, "days")
        _require_non_negative(self.price_per_unit, "price_per_unit")

    @property
    def projected_yield_units(self) -> float:
        """Projected yield in the native unit, continuous-ish compounding
        approximated as simple ``apy * days/365``."""
        return self.quantity * self.apy * (self.days / 365.0)

    @property
    def projected_yield_usd(self) -> float:
        return self.projected_yield_units * self.price_per_unit


@dataclass(frozen=True)
class Bond:
    """A Treasury bond or bond-like instrument, priced at face value.

    Attributes:
        label: Human-readable label, e.g. ``"10Y UST"``.
        face_value: Par/face value in USD.
        coupon_rate_annual: Coupon as a decimal (``0.045`` = 4.5%).
        years_to_maturity: Remaining time to maturity in years.
        price: Caller-supplied current market price (usually near
            ``face_value``).
    """

    label: str
    face_value: float
    coupon_rate_annual: float
    years_to_maturity: float
    price: float

    def __post_init__(self) -> None:
        _require_positive(self.face_value, "face_value")
        _require_non_negative(self.coupon_rate_annual, "coupon_rate_annual")
        _require_non_negative(self.years_to_maturity, "years_to_maturity")
        _require_positive(self.price, "price")

    @property
    def annual_coupon_income(self) -> float:
        return self.face_value * self.coupon_rate_annual

    @property
    def total_coupon_income(self) -> float:
        return self.annual_coupon_income * self.years_to_maturity

    @property
    def projected_total_return(self) -> float:
        """Projected total return at maturity = coupons + (face - price).

        This assumes buy-and-hold to maturity with no default. It is a
        simplification of yield-to-maturity, useful for a paper view.
        """
        return self.total_coupon_income + (self.face_value - self.price)


@dataclass(frozen=True)
class IPOAllocation:
    """A hypothetical IPO allocation.

    Attributes:
        symbol: Ticker the IPO will trade under.
        shares_allocated: Shares the user was (hypothetically) allocated.
        issue_price: Offer price per share.
        current_price: Caller-supplied current (or projected) price per
            share. Use the issue price for a pre-open view.
        lockup_days_remaining: Days until the shares can be sold. 0 if
            unlocked or not applicable.
    """

    symbol: str
    shares_allocated: float
    issue_price: float
    current_price: float
    lockup_days_remaining: float = 0.0

    def __post_init__(self) -> None:
        _require_non_negative(self.shares_allocated, "shares_allocated")
        _require_non_negative(self.issue_price, "issue_price")
        _require_non_negative(self.current_price, "current_price")
        _require_non_negative(
            self.lockup_days_remaining, "lockup_days_remaining"
        )

    @property
    def cost(self) -> float:
        return self.shares_allocated * self.issue_price

    @property
    def market_value(self) -> float:
        return self.shares_allocated * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost

    @property
    def locked(self) -> bool:
        return self.lockup_days_remaining > 0


@dataclass(frozen=True)
class PortfolioSummary:
    """Aggregated totals across every asset class.

    Every field is USD.
    """

    total_cost_basis: float
    total_market_value: float
    total_unrealized_pnl: float
    projected_staking_yield: float
    projected_bond_return: float
    projected_total_return: float


def summarize_portfolio(
    holdings: Iterable[CoinHolding] = (),
    staking: Iterable[StakingPosition] = (),
    bonds: Iterable[Bond] = (),
    ipos: Iterable[IPOAllocation] = (),
) -> PortfolioSummary:
    """Aggregate every paper position into a single summary.

    The result is projected, not actual. Nothing here settles a trade
    or moves a coin.
    """
    holdings_t = tuple(holdings)
    staking_t = tuple(staking)
    bonds_t = tuple(bonds)
    ipos_t = tuple(ipos)

    holdings_cost = sum(h.cost_basis for h in holdings_t)
    ipos_cost = sum(i.cost for i in ipos_t)
    bonds_cost = sum(b.price for b in bonds_t)
    total_cost_basis = holdings_cost + ipos_cost + bonds_cost

    holdings_value = sum(h.market_value for h in holdings_t)
    ipos_value = sum(i.market_value for i in ipos_t)
    bonds_value = sum(b.price for b in bonds_t)
    total_market_value = holdings_value + ipos_value + bonds_value

    holdings_pnl = sum(h.unrealized_pnl for h in holdings_t)
    ipos_pnl = sum(i.unrealized_pnl for i in ipos_t)
    total_unrealized_pnl = holdings_pnl + ipos_pnl

    projected_staking_yield = sum(s.projected_yield_usd for s in staking_t)
    projected_bond_return = sum(b.projected_total_return for b in bonds_t)
    projected_total_return = (
        total_unrealized_pnl
        + projected_staking_yield
        + projected_bond_return
    )

    return PortfolioSummary(
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized_pnl,
        projected_staking_yield=projected_staking_yield,
        projected_bond_return=projected_bond_return,
        projected_total_return=projected_total_return,
    )


__all__ = [
    "Bond",
    "CoinHolding",
    "IPOAllocation",
    "PortfolioSummary",
    "StakingPosition",
    "summarize_portfolio",
]
