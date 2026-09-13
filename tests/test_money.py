from decimal import Decimal

import pytest

from atlas.domain.money import allocate, cents

LARGE_SCHEDULE = 50  # the old float fast-path threshold; kept so the regression tests straddle it


def test_cents_rounds_half_up():
    assert cents(Decimal("1.005")) == Decimal("1.01")
    assert cents("2.994") == Decimal("2.99")


@pytest.mark.parametrize(
    "total,parts",
    [
        ("100.00", 3),
        ("7519.68", 6),
        ("1500.00", 7),
        ("0.05", 3),
        # ATLAS-39: Harbourview Towers, 113 lots, must still be cent-exact.
        ("61412.20", 113),
        ("61412.20", LARGE_SCHEDULE),
        ("61412.20", LARGE_SCHEDULE + 1),
        ("1500.00", 500),
    ],
)
def test_allocate_sums_exactly(total, parts):
    out = allocate(Decimal(total), parts)
    assert len(out) == parts
    assert sum(out) == Decimal(total)
    assert max(out) - min(out) <= Decimal("0.01")


@pytest.mark.parametrize("parts", [LARGE_SCHEDULE, LARGE_SCHEDULE + 1, 113, 500])
def test_allocate_entries_are_cent_exact_for_large_schedules(parts):
    """Every entry must be a whole number of cents, not just the sum.

    ATLAS-39: the large-schedule path used to compute float shares, which produced
    amounts like Decimal('543.5599999999965') that never round-trip to a clean cent.
    """
    out = allocate(Decimal("61412.20"), parts)
    for amount in out:
        assert amount == cents(amount)


def test_allocate_rejects_zero_parts():
    with pytest.raises(ValueError):
        allocate(Decimal(10), 0)
