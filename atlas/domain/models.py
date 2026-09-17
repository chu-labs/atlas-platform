"""Domain records. Plain dataclasses so repositories and tests can build them without a database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class Building:
    id: int
    plan_number: str
    name: str
    suburb: str
    state: str
    postcode: str
    year_built: int
    floors: int
    lots: int
    construction_type: str  # concrete | brick | timber | mixed
    roof_type: str  # tile | metal | concrete | membrane
    sprinklers: bool
    flood_zone: str  # none | low | high
    bushfire_bal: str  # none | low | 12.5 | 19 | 29 | 40 | FZ
    distance_to_coast_km: float
    cladding_flag: bool
    last_inspection: date | None
    lat: float = 0.0
    lng: float = 0.0


@dataclass(frozen=True)
class Broker:
    id: int
    name: str
    state: str


@dataclass(frozen=True)
class Policy:
    id: int
    policy_number: str
    building_id: int
    broker_id: int
    product: str  # residential_strata | commercial_strata
    inception_date: date
    expiry_date: date
    sum_insured: Decimal
    base_premium: Decimal
    status: str  # active | lapsed | cancelled
    excess: Decimal = Decimal(1000)


@dataclass(frozen=True)
class Claim:
    id: int
    claim_number: str
    policy_id: int
    building_id: int
    loss_date: date
    reported_date: date
    peril: str
    status: str  # open | closed | declined
    incurred: Decimal
    paid: Decimal
    description: str


@dataclass(frozen=True)
class RiskProfile:
    building_id: int
    score: int  # 0 (best) .. 100 (worst)
    band: str  # A | B | C | D | E
    pillars: dict[str, int]
    drivers: list[str]


@dataclass(frozen=True)
class Quote:
    policy_number: str
    quoted_at: datetime
    sum_insured: Decimal
    annual_premium: Decimal
    per_lot: list[Decimal]
    factors: dict[str, Decimal] = field(default_factory=dict)
