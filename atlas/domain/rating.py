"""Premium rating for a strata renewal.

premium = sum_insured * base_rate(product, state) * risk_factor * loadings - discounts, then a
minimum premium, then split cent-exactly across lots. All money is Decimal.

The high-rise loading (floors > 20) is a deliberate business rule: tall buildings carry more
liability and water exposure. Changing it is an underwriting decision, not a code fix.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .errors import BusinessRuleViolation
from .models import Building, Policy, Quote, RiskProfile
from .money import allocate, cents

BASE_RATE = {  # per dollar of sum insured, per year
    ("residential_strata", "NSW"): Decimal("0.00235"),
    ("residential_strata", "VIC"): Decimal("0.00210"),
    ("residential_strata", "QLD"): Decimal("0.00290"),
    ("residential_strata", "WA"): Decimal("0.00205"),
    ("residential_strata", "SA"): Decimal("0.00200"),
    ("residential_strata", "TAS"): Decimal("0.00195"),
    ("residential_strata", "ACT"): Decimal("0.00215"),
    ("residential_strata", "NT"): Decimal("0.00340"),
    ("commercial_strata", "NSW"): Decimal("0.00310"),
    ("commercial_strata", "VIC"): Decimal("0.00285"),
    ("commercial_strata", "QLD"): Decimal("0.00360"),
    ("commercial_strata", "WA"): Decimal("0.00280"),
    ("commercial_strata", "SA"): Decimal("0.00270"),
    ("commercial_strata", "TAS"): Decimal("0.00265"),
    ("commercial_strata", "ACT"): Decimal("0.00290"),
    ("commercial_strata", "NT"): Decimal("0.00420"),
}
MINIMUM_PREMIUM = Decimal("1500.00")
HIGH_RISE_FLOORS = 20
HIGH_RISE_LOADING = Decimal("1.15")


def risk_factor(profile: RiskProfile) -> Decimal:
    """Map the 0..100 score onto a 0.80 .. 1.60 multiplier."""
    return cents(Decimal("0.80") + Decimal(profile.score) / Decimal(100) * Decimal("0.80"))


def loadings(b: Building) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    if b.floors > HIGH_RISE_FLOORS:
        out["high_rise"] = HIGH_RISE_LOADING
    if b.cladding_flag:
        out["cladding"] = Decimal("1.25")
    if b.flood_zone == "high":
        out["flood"] = Decimal("1.30")
    if b.bushfire_bal in {"29", "40", "FZ"}:
        out["bushfire"] = Decimal("1.20")
    return out


def discounts(b: Building) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    if b.sprinklers:
        out["sprinklers"] = Decimal("0.95")
    if b.construction_type == "concrete" and b.year_built >= 2010:
        out["modern_concrete"] = Decimal("0.97")
    return out


def quote_renewal(policy: Policy, b: Building, profile: RiskProfile, now: datetime) -> Quote:
    rate = BASE_RATE[(policy.product, b.state)]
    factors: dict[str, Decimal] = {"base_rate": rate, "risk": risk_factor(profile)}
    premium = policy.sum_insured * rate * factors["risk"]
    for k, v in loadings(b).items():
        factors[k] = v
        premium *= v
    for k, v in discounts(b).items():
        factors[k] = v
        premium *= v
    premium = max(cents(premium), MINIMUM_PREMIUM)
    lots = max(b.lots, 1)
    per_lot = allocate(premium, lots)
    if sum(per_lot) != premium:
        # Reconciliation control: the lot schedule must add up to the invoiced premium to the cent.
        raise BusinessRuleViolation(
            "quote.allocation_mismatch",
            f"per-lot schedule sums to {sum(per_lot)} but premium is {premium} for {lots} lots",
            customer_impact=lots,
        )
    return Quote(
        policy_number=policy.policy_number,
        quoted_at=now,
        sum_insured=policy.sum_insured,
        annual_premium=premium,
        per_lot=per_lot,
        factors=factors,
    )
