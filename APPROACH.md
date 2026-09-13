# ATLAS-39 — Analyst notes: lot schedule doesn't sum to premium on large plans

## Root cause

`atlas/domain/money.py:14-30`, function `allocate(total, parts)`.

Commit `ab3e6fd` ("Fast path for large lot schedules") added a branch at
`atlas/domain/money.py:21-25` for `parts > LARGE_SCHEDULE` (50 lots):

```python
if parts > LARGE_SCHEDULE:
    share = round(float(total) / parts, 2)
    remainder = float(total) - share * parts
    return [Decimal(str(share + remainder))] + [Decimal(str(share))] * (parts - 1)
```

This does the split in `float`, not `Decimal`. `float(total) / parts` and the subsequent
`float(total) - share * parts` are binary floating point operations that cannot represent most
decimal cents exactly, so:

- `share` itself can be a float that doesn't round-trip to a clean 2-decimal value (`round()` on a
  float rounds the float, not the decimal).
- `remainder` is computed via float subtraction, compounding representation error instead of being
  an exact "leftover cents" integer count the way the Decimal path (`money.py:26-30`) computes it.
- The first element `Decimal(str(share + remainder))` inherits all of that float error and is
  never quantized to cents with `cents()`/`ROUND_HALF_UP`, unlike the normal path.

Reproduced directly:

```python
>>> allocate(Decimal("61412.20"), 113)
sum = Decimal('61412.1999999999965')   # != 61412.20
out[0] = Decimal('543.5599999999965')  # not cent-exact
```

This is exactly the Harbourview Towers symptom (113 lots, schedule off by a fraction of a cent,
serialized with the float's full repr). Plans with ≤50 lots never enter this branch, which matches
the report that smaller plans "look fine."

The caller, `quote_renewal` in `atlas/domain/rating.py:80-87`, already has a reconciliation guard
(`if sum(per_lot) != premium: raise BusinessRuleViolation(...)`) — this is the control mentioned in
CLAUDE.md that is *supposed* to catch exactly this, and for Harbourview it presumably did (or the
invoice-run's own summation check did, per the ticket). Either way this confirms the defect is in
`allocate`, not in the reconciliation logic, and not in the rating/business rules themselves
(`BASE_RATE`, `MINIMUM_PREMIUM`, loadings/discounts are untouched by this branch).

## Exact functions/lines involved

- `atlas/domain/money.py:14` — `allocate(total, parts)`, the function to fix.
- `atlas/domain/money.py:21-25` — the buggy float fast path to remove/replace.
- `atlas/domain/money.py:7` — `LARGE_SCHEDULE = 50` constant, only used to gate this branch.
- `atlas/domain/rating.py:80-87` — sole call site (`per_lot = allocate(premium, lots)`), plus the
  reconciliation raise. Not the bug location; do not change the rating logic here.
- `tests/test_money.py` — where new regression tests belong (parametrized `test_allocate_sums_exactly`
  currently only exercises `parts` in `{3, 6, 7}`, never crossing the 50-lot threshold — that's why
  this regression shipped untested).

## Smallest safe fix

Delete the `parts > LARGE_SCHEDULE` float branch entirely and let all part counts go through the
existing Decimal path (`money.py:26-30`), which is already correct and already proven cent-exact by
the current parametrized tests. That path is `O(parts)` and uses `Decimal` arithmetic throughout —
still fast enough for any realistic strata plan (hundreds of lots), so there is no real performance
justification for keeping a separate branch. This also lets `LARGE_SCHEDULE` be removed if it's no
longer referenced anywhere else (confirmed: `allocate` and the constant definition are the only two
references, plus the module docstring context — nothing else in `atlas/` or `tests/` reads
`LARGE_SCHEDULE`).

Do not touch the Decimal branch itself (`money.py:26-30`) — it is correct and is what the small-plan
tests already pin.

## Edge cases a test must cover

1. **The exact regression**: `allocate(Decimal("61412.20"), 113)` (or the literal Harbourview
   numbers) — sum must equal total exactly, and every element must be a cent-exact `Decimal`
   (no residual float noise when compared via `Decimal` equality/repr).
2. **A `parts` value just above the old threshold**: e.g. 51 lots, to pin the boundary that used to
   flip into the float path.
3. **A `parts` value well above it**: e.g. 500+ lots, to guard against any future reintroduction of
   a "fast path" for very large plans.
4. **Non-round total with large parts**: a total that doesn't divide evenly (e.g. an odd number of
   cents across 113 parts) to confirm remainder cents are still distributed as whole cents and land
   only on the expected number of lots (no lot should differ from another by more than $0.01 — the
   existing `max(out) - min(out) <= Decimal("0.01")` assertion pattern from the current parametrized
   test applies here too).
5. Keep the existing small-`parts` cases passing (3, 6, 7 lots, and the zero-parts `ValueError`) —
   this is a pure bug fix, not a behavior change for small plans.

Suggested approach: extend the existing `@pytest.mark.parametrize` list in `test_allocate_sums_exactly`
with large-`parts` cases (covers cases 1–4 with the existing assertions), rather than writing a
separate test function — the existing test already asserts exactly what matters (`sum(out) == total`
and max-min spread ≤ 1 cent).

## What must NOT change

- `atlas/domain/rating.py` — no changes to `BASE_RATE`, `MINIMUM_PREMIUM`, `HIGH_RISE_FLOORS`,
  `HIGH_RISE_LOADING`, loadings/discounts, or the `quote_renewal` reconciliation guard. The ticket
  is explicit: "Do not change the rating itself," and CLAUDE.md forbids changing business rules to
  make a bug go away — this bug is not a business rule, it's an arithmetic defect in `allocate`.
- The Decimal code path in `allocate` (`money.py:26-30`) that already handles ≤50-lot plans
  correctly — don't refactor it while fixing the large-plan path; the minimal diff is to delete the
  float branch.
- `migrations/` — not implicated, no schema involved.
- No new dependencies — the fix only removes code, it needs nothing new.
- The 30-day renewal notice / renewal-window inclusive-boundary rules in `renewals.py` — unrelated
  to this ticket, do not touch.
