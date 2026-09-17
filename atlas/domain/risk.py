"""Building risk score: five weighted pillars, 0 (best) to 100 (worst).

Pillars and weights:
  claims experience 35%, building fabric 20%, water 15%, natural hazard 20%, compliance 10%.
Each pillar scores 0..100; the weighted sum is the score. Bands: A <20, B <40, C <60, D <80, E.
"""

from __future__ import annotations

from datetime import date

from .models import Building, Claim, RiskProfile

WEIGHTS = {"claims": 35, "fabric": 20, "water": 15, "hazard": 20, "compliance": 10}
WATER_PERILS = {"water_damage", "storm", "flood"}


def _clamp(x: float, lo: float = 0, hi: float = 100) -> int:
    return round(max(lo, min(hi, x)))


def claims_pillar(b: Building, claims: list[Claim], as_of: date) -> tuple[int, list[str]]:
    """Frequency per lot and severity over the last five years drive this pillar."""
    recent = [c for c in claims if (as_of - c.loss_date).days <= 5 * 365 and c.status != "declined"]
    if not recent:
        return 5, []
    if b.lots <= 0:
        # A building with no lots cannot have a per-lot frequency; treat as a single risk unit.
        lots = 1
    else:
        lots = b.lots
    freq_per_lot_year = len(recent) / lots / 5
    incurred = sum((c.incurred for c in recent), start=0)
    severity = float(incurred) / len(recent)
    score = 20 + freq_per_lot_year * 400 + min(severity / 2000, 40)
    drivers = []
    if freq_per_lot_year > 0.1:
        drivers.append(f"high claims frequency ({len(recent)} claims in 5 years across {lots} lots)")
    if severity > 25000:
        drivers.append(f"high average claim severity (${severity:,.0f})")
    return _clamp(score), drivers


def fabric_pillar(b: Building, as_of: date) -> tuple[int, list[str]]:
    age = as_of.year - b.year_built
    score = min(age, 80) * 0.6
    drivers = []
    if b.construction_type == "timber":
        score += 25
        drivers.append("timber construction")
    elif b.construction_type == "mixed":
        score += 10
    if b.roof_type == "membrane":
        score += 10
    if b.cladding_flag:
        score += 30
        drivers.append("combustible cladding flagged")
    if age > 40:
        drivers.append(f"building age {age} years")
    return _clamp(score), drivers


def water_pillar(b: Building, claims: list[Claim], as_of: date) -> tuple[int, list[str]]:
    recent_water = [c for c in claims if c.peril in WATER_PERILS and (as_of - c.loss_date).days <= 3 * 365]
    score = 10 + len(recent_water) * 12
    if b.roof_type == "membrane":
        score += 10
    if b.floors >= 8:
        score += 8  # more risers, more leaks
    drivers = [f"{len(recent_water)} water-related claims in 3 years"] if len(recent_water) >= 3 else []
    return _clamp(score), drivers


def hazard_pillar(b: Building) -> tuple[int, list[str]]:
    score = 5.0
    drivers = []
    if b.flood_zone == "high":
        score += 45
        drivers.append("high flood zone")
    elif b.flood_zone == "low":
        score += 15
    bal = {"none": 0, "low": 5, "12.5": 12, "19": 20, "29": 30, "40": 40, "FZ": 55}.get(b.bushfire_bal, 0)
    score += bal
    if bal >= 20:
        drivers.append(f"bushfire attack level BAL-{b.bushfire_bal}")
    if b.distance_to_coast_km < 1:
        score += 15
        drivers.append("within 1 km of the coast")
    elif b.distance_to_coast_km < 5:
        score += 5
    return _clamp(score), drivers


def compliance_pillar(b: Building, as_of: date) -> tuple[int, list[str]]:
    if b.last_inspection is None:
        return 70, ["no recorded inspection"]
    years = (as_of - b.last_inspection).days / 365
    score = 5 + years * 15
    if not b.sprinklers and b.floors > 3:
        score += 20
    drivers = [f"last inspection {years:.1f} years ago"] if years > 3 else []
    return _clamp(score), drivers


def band(score: int) -> str:
    return "A" if score < 20 else "B" if score < 40 else "C" if score < 60 else "D" if score < 80 else "E"


def risk_profile(b: Building, claims: list[Claim], as_of: date) -> RiskProfile:
    parts = {
        "claims": claims_pillar(b, claims, as_of),
        "fabric": fabric_pillar(b, as_of),
        "water": water_pillar(b, claims, as_of),
        "hazard": hazard_pillar(b),
        "compliance": compliance_pillar(b, as_of),
    }
    pillars = {k: v[0] for k, v in parts.items()}
    drivers = [d for v in parts.values() for d in v[1]]
    score = _clamp(sum(pillars[k] * WEIGHTS[k] for k in WEIGHTS) / 100)
    return RiskProfile(building_id=b.id, score=score, band=band(score), pillars=pillars, drivers=drivers)
