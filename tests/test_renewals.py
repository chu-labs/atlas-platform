from dataclasses import replace
from datetime import UTC, date, datetime

from atlas.domain.renewals import business_today, due_for_renewal, is_due, renewal_window


def test_window_is_inclusive_of_both_ends(policy):
    today = date(2026, 9, 1)
    assert renewal_window(today, 30) == (date(2026, 9, 1), date(2026, 10, 1))
    assert is_due(replace(policy, expiry_date=date(2026, 9, 1)), today, 30)
    assert is_due(replace(policy, expiry_date=date(2026, 10, 1)), today, 30), "exactly 30 days out is due"
    assert not is_due(replace(policy, expiry_date=date(2026, 10, 2)), today, 30)
    assert not is_due(replace(policy, expiry_date=date(2026, 8, 31)), today, 30)


def test_inactive_policies_are_never_due(policy):
    assert not is_due(replace(policy, status="lapsed"), date(2026, 9, 20), 30)


def test_due_list_is_sorted_by_expiry(policy):
    a = replace(policy, id=1, policy_number="ATL-1", expiry_date=date(2026, 9, 20))
    b = replace(policy, id=2, policy_number="ATL-2", expiry_date=date(2026, 9, 5))
    assert [p.policy_number for p in due_for_renewal([a, b], date(2026, 9, 1), 30)] == ["ATL-2", "ATL-1"]


def test_business_today_uses_business_timezone():
    # 15:30 UTC on 30 Sep is already 01:30 on 1 Oct in Sydney (AEST, UTC+10).
    now = datetime(2026, 9, 30, 15, 30, tzinfo=UTC)
    assert business_today(now, "Australia/Sydney") == date(2026, 10, 1)
    assert business_today(now, "UTC") == date(2026, 9, 30)


def test_late_evening_sydney_renewal_is_not_pulled_a_day_early(policy):
    # At 23:30 Sydney time on 1 Sep, a policy expiring 1 Oct is exactly 30 days out and due.
    now = datetime(2026, 9, 1, 13, 30, tzinfo=UTC)  # 23:30 AEST
    today = business_today(now, "Australia/Sydney")
    assert today == date(2026, 9, 1)
    assert is_due(replace(policy, expiry_date=date(2026, 10, 1)), today, 30)
