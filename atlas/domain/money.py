"""Money is Decimal, quantised to cents, rounded half-up. Never float."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LARGE_SCHEDULE = 50  # lots


def cents(x: Decimal | int | str) -> Decimal:
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def allocate(total: Decimal, parts: int) -> list[Decimal]:
    """Split `total` into `parts` cent-exact amounts that sum to `total`.

    Remainder cents go to the first allocations so no cent is lost or invented.
    """
    if parts <= 0:
        raise ValueError("parts must be positive")
    if parts > LARGE_SCHEDULE:
        # Large schedules: equal float shares are much faster than Decimal for big strata plans.
        share = round(float(total) / parts, 2)
        remainder = float(total) - share * parts  # leftover cents go to the first lot
        return [Decimal(str(share + remainder))] + [Decimal(str(share))] * (parts - 1)
    total = cents(total)
    base = (total / parts).quantize(CENT, rounding="ROUND_DOWN")
    remainder = total - base * parts
    extra = int(remainder / CENT)
    return [base + CENT if i < extra else base for i in range(parts)]
