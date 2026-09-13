from decimal import Decimal

import pytest

from atlas.domain.money import allocate, cents


def test_cents_rounds_half_up():
    assert cents(Decimal("1.005")) == Decimal("1.01")
    assert cents("2.994") == Decimal("2.99")


@pytest.mark.parametrize(
    "total,parts",
    [
        ("100.00", 3),
        ("7519.68", 6),
        ("1500.00", 7),
        ("12345.67", 113),
        ("0.05", 3),
        ("61412.20", 113),
        ("999999.99", 251),
    ],
)
def test_allocate_sums_exactly(total, parts):
    out = allocate(Decimal(total), parts)
    assert len(out) == parts
    assert sum(out) == Decimal(total)
    assert max(out) - min(out) <= Decimal("0.01")


def test_allocate_rejects_zero_parts():
    with pytest.raises(ValueError):
        allocate(Decimal(10), 0)
