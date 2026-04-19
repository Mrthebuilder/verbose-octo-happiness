from __future__ import annotations

import pytest

from software.portfolio import (
    Bond,
    CoinHolding,
    IPOAllocation,
    StakingPosition,
    summarize_portfolio,
)


def test_coin_holding_pnl() -> None:
    h = CoinHolding(
        symbol="ETH",
        quantity=2.0,
        cost_basis_per_unit=2500.0,
        current_price_per_unit=3200.0,
    )
    assert h.cost_basis == pytest.approx(5000.0)
    assert h.market_value == pytest.approx(6400.0)
    assert h.unrealized_pnl == pytest.approx(1400.0)


def test_staking_yield_is_linear() -> None:
    s = StakingPosition(
        symbol="ETH",
        quantity=10.0,
        apy=0.04,
        days=365.0,
        price_per_unit=3000.0,
    )
    assert s.projected_yield_units == pytest.approx(0.4)
    assert s.projected_yield_usd == pytest.approx(1200.0)


def test_bond_total_return() -> None:
    b = Bond(
        label="10Y UST",
        face_value=10_000.0,
        coupon_rate_annual=0.045,
        years_to_maturity=10.0,
        price=9_800.0,
    )
    assert b.annual_coupon_income == pytest.approx(450.0)
    assert b.total_coupon_income == pytest.approx(4500.0)
    # Coupons + (face - price) discount = 4500 + 200 = 4700.
    assert b.projected_total_return == pytest.approx(4700.0)


def test_ipo_lockup_and_pnl() -> None:
    locked = IPOAllocation(
        symbol="LOCKED",
        shares_allocated=100.0,
        issue_price=20.0,
        current_price=30.0,
        lockup_days_remaining=90.0,
    )
    assert locked.locked is True
    assert locked.unrealized_pnl == pytest.approx(1000.0)

    open_ipo = IPOAllocation(
        symbol="OPEN",
        shares_allocated=50.0,
        issue_price=20.0,
        current_price=15.0,
    )
    assert open_ipo.locked is False
    assert open_ipo.unrealized_pnl == pytest.approx(-250.0)


def test_summarize_portfolio_aggregates_every_section() -> None:
    summary = summarize_portfolio(
        holdings=[
            CoinHolding(
                symbol="ETH",
                quantity=2.0,
                cost_basis_per_unit=2500.0,
                current_price_per_unit=3000.0,
            ),
        ],
        staking=[
            StakingPosition(
                symbol="ETH",
                quantity=2.0,
                apy=0.05,
                days=365.0,
                price_per_unit=3000.0,
            ),
        ],
        bonds=[
            Bond(
                label="1Y",
                face_value=1000.0,
                coupon_rate_annual=0.05,
                years_to_maturity=1.0,
                price=1000.0,
            ),
        ],
        ipos=[
            IPOAllocation(
                symbol="EXAMPL",
                shares_allocated=10.0,
                issue_price=10.0,
                current_price=12.0,
            ),
        ],
    )
    # Holdings: cost 5000, value 6000, pnl 1000.
    # IPO: cost 100, value 120, pnl 20.
    # Bonds: cost = value = 1000.
    assert summary.total_cost_basis == pytest.approx(6100.0)
    assert summary.total_market_value == pytest.approx(7120.0)
    assert summary.total_unrealized_pnl == pytest.approx(1020.0)
    # Staking: 2 * 0.05 * 1 * 3000 = 300.
    assert summary.projected_staking_yield == pytest.approx(300.0)
    # Bond: coupon 50 + (face 1000 - price 1000) = 50.
    assert summary.projected_bond_return == pytest.approx(50.0)
    assert summary.projected_total_return == pytest.approx(1370.0)


def test_summarize_empty_portfolio_is_zero() -> None:
    summary = summarize_portfolio()
    assert summary.total_cost_basis == 0.0
    assert summary.total_market_value == 0.0
    assert summary.total_unrealized_pnl == 0.0
    assert summary.projected_staking_yield == 0.0
    assert summary.projected_bond_return == 0.0
    assert summary.projected_total_return == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": -1.0, "cost_basis_per_unit": 10.0, "current_price_per_unit": 10.0},
        {"quantity": 1.0, "cost_basis_per_unit": -1.0, "current_price_per_unit": 10.0},
        {"quantity": 1.0, "cost_basis_per_unit": 10.0, "current_price_per_unit": -1.0},
    ],
)
def test_coin_holding_rejects_negatives(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        CoinHolding(symbol="X", **kwargs)
