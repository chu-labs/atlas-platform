"""Repositories: SQL in, domain records out. Keep queries here and only here."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..domain.models import Broker, Building, Claim, Policy
from .pool import conn


def _building(r: dict) -> Building:
    return Building(**{k: r[k] for k in Building.__dataclass_fields__})


def _policy(r: dict) -> Policy:
    return Policy(**{k: r[k] for k in Policy.__dataclass_fields__})


def _claim(r: dict) -> Claim:
    return Claim(**{k: r[k] for k in Claim.__dataclass_fields__})


def get_building(building_id: int) -> Building | None:
    with conn() as c:
        r = c.execute("select * from buildings where id = %s", (building_id,)).fetchone()
    return _building(r) if r else None


def get_building_by_plan(plan_number: str) -> Building | None:
    with conn() as c:
        r = c.execute("select * from buildings where plan_number = %s", (plan_number,)).fetchone()
    return _building(r) if r else None


def list_buildings(state: str | None = None, limit: int = 50, offset: int = 0) -> list[Building]:
    with conn() as c:
        if state:
            rows = c.execute(
                "select * from buildings where state = %s order by id limit %s offset %s", (state, limit, offset)
            ).fetchall()
        else:
            rows = c.execute("select * from buildings order by id limit %s offset %s", (limit, offset)).fetchall()
    return [_building(r) for r in rows]


def get_policy(policy_number: str) -> Policy | None:
    with conn() as c:
        r = c.execute("select * from policies where policy_number = %s", (policy_number,)).fetchone()
    return _policy(r) if r else None


def policies_for_building(building_id: int) -> list[Policy]:
    with conn() as c:
        rows = c.execute("select * from policies where building_id = %s order by expiry_date", (building_id,)).fetchall()
    return [_policy(r) for r in rows]


def active_policies_expiring_between(start: date, end: date) -> list[Policy]:
    """Active policies whose expiry falls in the inclusive [start, end] window."""
    with conn() as c:
        rows = c.execute(
            "select * from policies where status = 'active' and expiry_date between %s and %s "
            "order by expiry_date, policy_number",
            (start, end),
        ).fetchall()
    return [_policy(r) for r in rows]


def buildings_by_ids(ids: list[int]) -> dict[int, Building]:
    """Fetch many buildings in one query. Use this when listing policies to avoid N+1."""
    if not ids:
        return {}
    with conn() as c:
        rows = c.execute("select * from buildings where id = any(%s)", (ids,)).fetchall()
    return {r["id"]: _building(r) for r in rows}


def claims_for_building(building_id: int) -> list[Claim]:
    with conn() as c:
        rows = c.execute(
            "select * from claims where building_id = %s order by loss_date desc", (building_id,)
        ).fetchall()
    return [_claim(r) for r in rows]


def claims_for_policy(policy_id: int) -> list[Claim]:
    with conn() as c:
        rows = c.execute("select * from claims where policy_id = %s order by loss_date desc", (policy_id,)).fetchall()
    return [_claim(r) for r in rows]


def get_broker(broker_id: int) -> Broker | None:
    with conn() as c:
        r = c.execute("select * from brokers where id = %s", (broker_id,)).fetchone()
    return Broker(**r) if r else None


def save_quote(policy_id: int, premium: Decimal, factors: dict) -> None:
    import json

    with conn() as c:
        c.execute(
            "insert into renewal_quotes(policy_id, annual_premium, factors) values (%s, %s, %s)",
            (policy_id, premium, json.dumps({k: str(v) for k, v in factors.items()})),
        )


def portfolio_stats() -> dict:
    with conn() as c:
        row = c.execute(
            """
            select
              (select count(*) from buildings) as buildings,
              (select count(*) from policies where status = 'active') as active_policies,
              (select coalesce(sum(sum_insured),0) from policies where status = 'active') as sum_insured,
              (select coalesce(sum(base_premium),0) from policies where status = 'active') as gwp,
              (select count(*) from claims where status = 'open') as open_claims,
              (select coalesce(sum(incurred),0) from claims) as incurred
            """
        ).fetchone()
        by_state = c.execute(
            "select state, count(*) as policies, sum(base_premium) as gwp from policies p "
            "join buildings b on b.id = p.building_id where p.status='active' group by state order by gwp desc"
        ).fetchall()
        perils = c.execute(
            "select peril, count(*) as n, sum(incurred) as incurred from claims group by peril order by n desc"
        ).fetchall()
    return {**row, "by_state": by_state, "perils": perils}


def save_ai_report(kind: str, subject_key: str, model: str, content: str, input_tokens: int, output_tokens: int) -> int:
    with conn() as c:
        r = c.execute(
            "insert into ai_reports(kind, subject_key, model, content, input_tokens, output_tokens) "
            "values (%s,%s,%s,%s,%s,%s) returning id",
            (kind, subject_key, model, content, input_tokens, output_tokens),
        ).fetchone()
    return r["id"]


def latest_ai_report(kind: str, subject_key: str) -> dict | None:
    with conn() as c:
        return c.execute(
            "select * from ai_reports where kind=%s and subject_key=%s order by created_at desc limit 1",
            (kind, subject_key),
        ).fetchone()
