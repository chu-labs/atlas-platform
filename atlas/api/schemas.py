"""Response shapes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class BuildingOut(BaseModel):
    id: int
    plan_number: str
    name: str
    suburb: str
    state: str
    postcode: str
    year_built: int
    floors: int
    lots: int
    construction_type: str
    roof_type: str
    sprinklers: bool
    flood_zone: str
    bushfire_bal: str
    distance_to_coast_km: float
    cladding_flag: bool
    last_inspection: date | None


class PolicyOut(BaseModel):
    policy_number: str
    building_id: int
    building_name: str | None = None
    plan_number: str | None = None
    state: str | None = None
    broker_id: int
    product: str
    inception_date: date
    expiry_date: date
    days_until_expiry: int | None = None
    sum_insured: Decimal
    base_premium: Decimal
    status: str


class ClaimOut(BaseModel):
    claim_number: str
    policy_id: int
    loss_date: date
    reported_date: date
    peril: str
    status: str
    incurred: Decimal
    paid: Decimal
    description: str


class RiskOut(BaseModel):
    building_id: int
    score: int
    band: str
    pillars: dict[str, int]
    drivers: list[str]


class QuoteOut(BaseModel):
    policy_number: str
    quoted_at: datetime
    sum_insured: Decimal
    annual_premium: Decimal
    per_lot: list[Decimal]
    factors: dict[str, Decimal]


class AIReportOut(BaseModel):
    id: int
    kind: str
    subject_key: str
    model: str
    created_at: datetime
    input_tokens: int
    output_tokens: int
    content: str
