"""AI reports over the portfolio: building report, underwriting advice, claims summary.

Each report gathers structured facts from the repositories, asks the model for prose, and stores
the result. Reports are cached per subject until `refresh=True`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import HTTPException

from .db import repo
from .domain import rating, renewals, risk
from .settings import settings

SYSTEM = (
    "You are ATLAS, an underwriting assistant for an Australian strata insurer. Write for an "
    "underwriter: concrete, numeric where the data supports it, no filler. Use Australian English. "
    "Use markdown headings and short paragraphs. Never invent facts that are not in the data."
)


@lru_cache
def _client():
    import anthropic

    return anthropic.Anthropic(api_key=settings().anthropic_api_key)


def _ask(kind: str, subject_key: str, prompt: str, refresh: bool) -> dict:
    if not refresh:
        cached = repo.latest_ai_report(kind, subject_key)
        if cached:
            return cached
    if not settings().anthropic_api_key:
        raise HTTPException(503, "AI features are not configured (no ANTHROPIC_API_KEY)")
    msg = _client().messages.create(
        model=settings().anthropic_model,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    content = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    rid = repo.save_ai_report(
        kind, subject_key, msg.model, content, msg.usage.input_tokens, msg.usage.output_tokens
    )
    return repo.latest_ai_report(kind, subject_key) | {"id": rid}


def _today():
    return renewals.business_today(datetime.now(UTC), settings().business_tz)


def _building_facts(building_id: int) -> tuple[dict, list, object]:
    b = repo.get_building(building_id)
    if not b:
        raise HTTPException(404, "building not found")
    claims = repo.claims_for_building(b.id)
    profile = risk.risk_profile(b, claims, _today())
    facts = {
        "building": b.__dict__,
        "risk": profile.__dict__,
        "policies": [p.__dict__ for p in repo.policies_for_building(b.id)],
        "claims": [c.__dict__ for c in claims[:60]],
        "claim_count": len(claims),
    }
    return facts, claims, profile


def building_report(building_id: int, refresh: bool = False) -> dict:
    facts, _, _ = _building_facts(building_id)
    prompt = (
        "Write a building risk report for an underwriter with sections: Summary, Building profile, "
        "Risk score and drivers, Claims history, Recommended actions.\n\nDATA:\n"
        + json.dumps(facts, default=str)
    )
    return _ask("building_report", str(building_id), prompt, refresh)


def claims_summary(building_id: int, refresh: bool = False) -> dict:
    facts, claims, _ = _building_facts(building_id)
    prompt = (
        "Summarise this building's claims history: frequency and severity trends by year and peril, "
        "open claims, recurring causes, and what it implies for renewal terms.\n\nDATA:\n"
        + json.dumps({"building": facts["building"], "claims": [c.__dict__ for c in claims]}, default=str)
    )
    return _ask("claims_summary", str(building_id), prompt, refresh)


def underwriting_advice(policy_number: str, refresh: bool = False) -> dict:
    p = repo.get_policy(policy_number)
    if not p:
        raise HTTPException(404, "policy not found")
    facts, _claims, profile = _building_facts(p.building_id)
    b = repo.get_building(p.building_id)
    quote = rating.quote_renewal(p, b, profile, datetime.now(UTC))
    prompt = (
        "Give underwriting advice for this renewal: recommend renew / renew with conditions / decline, "
        "proposed premium versus expiring, excess and conditions, and the three facts that most drive "
        "the recommendation.\n\nDATA:\n"
        + json.dumps({**facts, "policy": p.__dict__, "quote": quote.__dict__}, default=str)
    )
    return _ask("underwriting_advice", policy_number, prompt, refresh)
