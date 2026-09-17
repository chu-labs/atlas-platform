from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from atlas.domain.renewals import business_today, due_for_renewal, is_due, renewal_window


def test_window_is_inclusive_of_both_ends(policy):
    today = date(2026, 9, 1)
    assert renewal_window(today, 30) == (date(2026, 9, 1), date(2026, 10, 1))
    assert is_due(replace(policy, expiry_date=date(2026, 9, 1)), today, 30)
    assert is_due(replace(policy, expiry_date=date(2026, 10, 1)), today, 30), "exactly 30 days out is due"
    assert not is_due(replace(policy, expiry_date=date(2026, 10, 2)), today, 30)
    assert not is_due(replace(policy, expiry_date=date(2026, 8, 31)), today, 30)


@pytest.mark.parametrize("days", [0, 7, 14, 90])
def test_window_end_is_today_plus_days_for_other_sizes(policy, days):
    today = date(2026, 9, 1)
    expected_end = today + timedelta(days=days)
    assert renewal_window(today, days) == (today, expected_end)
    assert is_due(replace(policy, expiry_date=expected_end), today, days), f"exactly {days} days out is due"
    assert not is_due(replace(policy, expiry_date=expected_end + timedelta(days=1)), today, days)


def test_window_crosses_a_leap_day(policy):
    today = date(2028, 2, 28)  # 2028 is a leap year
    assert renewal_window(today, 1) == (date(2028, 2, 28), date(2028, 2, 29))
    assert is_due(replace(policy, expiry_date=date(2028, 2, 29)), today, 1)


def test_atlas_38_14_day_run_includes_policies_expiring_exactly_14_days_out(policy):
    """Literal reproduction of ATLAS-38: 6 active policies expiring 2026-10-01 were missing
    from the 14-day run because renewal_window(2026-09-17, 14) stopped one day short."""
    today = date(2026, 9, 17)
    assert renewal_window(today, 14) == (date(2026, 9, 17), date(2026, 10, 1))
    assert is_due(replace(policy, expiry_date=date(2026, 10, 1)), today, 14)


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


def test_policy_is_in_force_on_its_expiry_date(policy):
    from atlas.domain.renewals import has_expired

    assert not has_expired(replace(policy, expiry_date=date(2026, 9, 13)), date(2026, 9, 13))
    assert has_expired(replace(policy, expiry_date=date(2026, 9, 12)), date(2026, 9, 13))
