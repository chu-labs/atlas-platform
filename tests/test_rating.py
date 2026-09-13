from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from atlas.domain.rating import (
    HIGH_RISE_FLOORS,
    HIGH_RISE_LOADING,
    MINIMUM_PREMIUM,
    quote_renewal,
    risk_factor,
)
from atlas.domain.risk import risk_profile

NOW = datetime(2026, 9, 13, tzinfo=UTC)
AS_OF = date(2026, 9, 13)


def _quote(policy, building, claims=()):
    return quote_renewal(policy, building, risk_profile(building, list(claims), AS_OF), NOW)


def test_premium_is_decimal_cents_and_per_lot_sums_exactly(policy, building):
    q = _quote(policy, building)
    assert isinstance(q.annual_premium, Decimal)
    assert q.annual_premium == q.annual_premium.quantize(Decimal("0.01"))
    assert len(q.per_lot) == building.lots
    assert sum(q.per_lot) == q.annual_premium


def test_per_lot_split_is_exact_for_awkward_lot_counts(policy, building):
    for lots in (3, 7, 11, 13, 97, 113):
        q = _quote(policy, replace(building, lots=lots))
        assert sum(q.per_lot) == q.annual_premium, lots


def test_minimum_premium_applies(policy, building):
    q = _quote(replace(policy, sum_insured=Decimal(100000)), building)
    assert q.annual_premium == MINIMUM_PREMIUM


def test_risk_factor_range(building):
    p = risk_profile(building, [], AS_OF)
    assert Decimal("0.80") <= risk_factor(p) <= Decimal("1.60")


def test_high_rise_loading_is_applied_above_threshold(policy, building):
    low = _quote(policy, replace(building, floors=HIGH_RISE_FLOORS))
    high = _quote(policy, replace(building, floors=HIGH_RISE_FLOORS + 1))
    assert "high_rise" not in low.factors
    assert high.factors["high_rise"] == HIGH_RISE_LOADING
    assert high.annual_premium > low.annual_premium


def test_sprinklers_discount(policy, building):
    with_ = _quote(policy, replace(building, sprinklers=True))
    without = _quote(policy, replace(building, sprinklers=False))
    assert with_.annual_premium < without.annual_premium
