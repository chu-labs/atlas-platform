"""Renewal window logic. Dates are business dates in the business timezone."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .models import Policy


def business_today(now: datetime, tz: str) -> date:
    """The calendar date in the business timezone for an aware instant `now`."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(ZoneInfo(tz)).date()


def renewal_window(today: date, days: int) -> tuple[date, date]:
    """Inclusive [today, today + days] window of expiry dates that are due for renewal."""
    return today, today + timedelta(days=days)


def is_due(policy: Policy, today: date, days: int = 30) -> bool:
    start, end = renewal_window(today, days)
    return policy.status == "active" and start <= policy.expiry_date <= end


def due_for_renewal(policies: list[Policy], today: date, days: int = 30) -> list[Policy]:
    return sorted((p for p in policies if is_due(p, today, days)), key=lambda p: (p.expiry_date, p.policy_number))


def days_until_expiry(policy: Policy, today: date) -> int:
    return (policy.expiry_date - today).days
