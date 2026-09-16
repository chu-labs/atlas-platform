"""HTTP routes. Thin: parse, call repositories and domain functions, shape the response."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from ..db import repo
from ..domain import rating, renewals, risk
from ..domain.errors import BusinessRuleViolation
from ..settings import settings
from .schemas import AIReportOut, BuildingOut, ClaimOut, PolicyOut, QuoteOut, RiskOut

router = APIRouter(prefix="/api")


def _now() -> datetime:
    return datetime.now(UTC)


def _today():
    return renewals.business_today(_now(), settings().business_tz)


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(
    due_within_days: int | None = Query(None, ge=0, le=365, description="Only policies due for renewal in this window"),
    limit: int = Query(100, ge=1, le=500),
):
    today = _today()
    if due_within_days is None:
        start, end = today, today.replace(year=today.year + 1)
    else:
        start, end = renewals.renewal_window(today, due_within_days)
    policies = repo.active_policies_expiring_between(start, end)[:limit]
    buildings = repo.buildings_by_ids([p.building_id for p in policies])
    out = []
    for p in policies:
        b = buildings.get(p.building_id)
        out.append(
            PolicyOut(
                **{k: getattr(p, k) for k in PolicyOut.model_fields if hasattr(p, k)},
                building_name=b.name if b else None,
                plan_number=b.plan_number if b else None,
                state=b.state if b else None,
                days_until_expiry=renewals.days_until_expiry(p, today),
            )
        )
    return out


@router.get("/renewals/reconcile")
def reconcile_renewals(days: int = Query(30, ge=1, le=365)):
    """Control: every active policy expiring within `days` must appear in the renewal run.

    Compares the renewal window used by the API with a direct count. A mismatch is a business-rule
    violation because policyholders would miss their renewal notice.
    """
    today = _today()
    start, end = renewals.renewal_window(today, days)
    in_run = {p.policy_number for p in repo.active_policies_expiring_between(start, end)}
    expected = repo.active_policies_expiring_between(today, today + timedelta(days=days))
    missing = [p for p in expected if p.policy_number not in in_run]
    if missing:
        dates = sorted({str(p.expiry_date) for p in missing})
        raise BusinessRuleViolation(
            "renewals.window_mismatch",
            f"{len(missing)} active policies expiring on {', '.join(dates)} are missing from the {days}-day renewal run",
            customer_impact=len(missing),
        )
    return {"days": days, "window": [str(start), str(end)], "policies": len(in_run), "missing": 0}


@router.get("/policies/{policy_number}", response_model=PolicyOut)
def get_policy(policy_number: str):
    p = repo.get_policy(policy_number)
    if not p:
        raise HTTPException(404, "policy not found")
    b = repo.get_building(p.building_id)
    return PolicyOut(
        **{k: getattr(p, k) for k in PolicyOut.model_fields if hasattr(p, k)},
        building_name=b.name if b else None,
        plan_number=b.plan_number if b else None,
        state=b.state if b else None,
        days_until_expiry=renewals.days_until_expiry(p, _today()),
    )


@router.post("/policies/{policy_number}/quote", response_model=QuoteOut)
def quote_policy(policy_number: str):
    p = repo.get_policy(policy_number)
    if not p:
        raise HTTPException(404, "policy not found")
    if p.status != "active":
        raise BusinessRuleViolation("quote.inactive_policy", f"{policy_number} is {p.status}; only active policies can be quoted")
    if renewals.has_expired(p, _today()):
        raise BusinessRuleViolation(
            "quote.expired_policy", f"{policy_number} expired on {p.expiry_date}; renewal must be re-underwritten"
        )
    b = repo.get_building(p.building_id)
    profile = risk.risk_profile(b, repo.claims_for_building(b.id), _today())
    q = rating.quote_renewal(p, b, profile, _now())
    repo.save_quote(p.id, q.annual_premium, q.factors)
    return QuoteOut(**q.__dict__)


@router.get("/policies/{policy_number}/claims", response_model=list[ClaimOut])
def policy_claims(policy_number: str):
    p = repo.get_policy(policy_number)
    if not p:
        raise HTTPException(404, "policy not found")
    return [ClaimOut(**c.__dict__) for c in repo.claims_for_policy(p.id)]


@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings(state: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = 0):
    return [BuildingOut(**b.__dict__) for b in repo.list_buildings(state, limit, offset)]


@router.get("/buildings/{building_id}", response_model=BuildingOut)
def get_building(building_id: int):
    b = repo.get_building(building_id)
    if not b:
        raise HTTPException(404, "building not found")
    return BuildingOut(**b.__dict__)


@router.get("/buildings/{building_id}/risk", response_model=RiskOut)
def building_risk(building_id: int):
    b = repo.get_building(building_id)
    if not b:
        raise HTTPException(404, "building not found")
    profile = risk.risk_profile(b, repo.claims_for_building(b.id), _today())
    return RiskOut(**profile.__dict__)


@router.get("/buildings/{building_id}/claims", response_model=list[ClaimOut])
def building_claims(building_id: int):
    if not repo.get_building(building_id):
        raise HTTPException(404, "building not found")
    return [ClaimOut(**c.__dict__) for c in repo.claims_for_building(building_id)]


@router.get("/buildings/{building_id}/policies", response_model=list[PolicyOut])
def building_policies(building_id: int):
    b = repo.get_building(building_id)
    if not b:
        raise HTTPException(404, "building not found")
    today = _today()
    return [
        PolicyOut(
            **{k: getattr(p, k) for k in PolicyOut.model_fields if hasattr(p, k)},
            building_name=b.name,
            plan_number=b.plan_number,
            state=b.state,
            days_until_expiry=renewals.days_until_expiry(p, today),
        )
        for p in repo.policies_for_building(building_id)
    ]


@router.get("/stats")
def stats():
    return repo.portfolio_stats()


# --- AI reports -------------------------------------------------------------


@router.post("/ai/building-report/{building_id}", response_model=AIReportOut)
def building_report(building_id: int, refresh: bool = False):
    from .. import ai

    return AIReportOut(**ai.building_report(building_id, refresh=refresh))


@router.post("/ai/underwriting-advice/{policy_number}", response_model=AIReportOut)
def underwriting_advice(policy_number: str, refresh: bool = False):
    from .. import ai

    return AIReportOut(**ai.underwriting_advice(policy_number, refresh=refresh))


@router.post("/ai/claims-summary/{building_id}", response_model=AIReportOut)
def claims_summary(building_id: int, refresh: bool = False):
    from .. import ai

    return AIReportOut(**ai.claims_summary(building_id, refresh=refresh))


@router.get("/ai/reports/{kind}/{subject_key}", response_model=AIReportOut)
def latest_report(kind: str, subject_key: str):
    r = repo.latest_ai_report(kind, subject_key)
    if not r:
        raise HTTPException(404, "no report yet")
    return AIReportOut(**r)
