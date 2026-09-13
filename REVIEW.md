# Review: ATLAS-39 — Lot schedule cent-exactness on large strata plans

**Branch reviewed:** `workbench/ATLAS-39/builder` (identical to `workbench/ATLAS-39/reviewer` HEAD)
**Diff:** `main...HEAD`, single commit `08a34e1`, single file changed (`atlas/domain/money.py`, 6 lines removed, 0 added)

## Verdict: **Request changes**

The fix itself is correct and exactly right in scope. It should not be re-approved on a rewrite — it
needs one thing added: a regression test that actually exercises the lot count where the bug occurred.
See "Test coverage gap" below; that's the blocking item.

## What the diff does

`atlas/domain/money.py:13-24` (`allocate`) previously special-cased `parts > LARGE_SCHEDULE` (50) by
computing shares as `float`, which is exactly how `$61,412.20` became `$61,412.2000000000001` for
Harbourview Towers' 113 lots (binary float can't represent `0.20` exactly, and the error compounds
over 113 additions/subtractions). The fix deletes the float branch and constant entirely, so every
lot count — regardless of size — goes through the pre-existing Decimal remainder-distribution
algorithm (quantize `ROUND_DOWN`, hand out leftover cents to the first N allocations). That algorithm
is unchanged and was already correct for small schedules; the fix just stops bypassing it.

Confirmed no dangling references to the removed `LARGE_SCHEDULE` constant anywhere else in
`atlas/` or `tests/` (`grep -rn "LARGE_SCHEDULE\|allocate(" atlas tests`).

## Correctness

- `atlas/domain/money.py:18-19` still guards `parts <= 0` before any division — no division-by-zero
  regression, "zero lots is one risk unit" is handled upstream in `risk.py`/`rating.py`, not touched here.
- The remainder-distribution algorithm (`atlas/domain/money.py:20-24`) sums to `total` by construction:
  `base * parts + extra * CENT == total` since `remainder` is derived directly from `total - base*parts`
  and `total` is already cent-quantized. This holds for any `parts`, so removing the float shortcut is
  sufficient — no algorithmic change was needed, which is the right minimal fix.
- Full suite green, ruff clean (`uv run pytest`, `uv run ruff check atlas tests` — verified locally).

## Business rules

None touched. `rating.py`, `risk.py`, `renewals.py` are untouched; only the allocation helper in
`money.py` changed, and only by removing an incorrect optimization — no rate, loading, threshold, or
window logic was modified. This is squarely "fix broken behaviour," not "change a business outcome,"
so no escalation was warranted here.

## Scope

Minimal and correctly scoped: one file, pure deletion, no unrelated cleanup, no dependency changes,
no migration changes. Commit message correctly states root cause and fix. Good discipline — nothing
to flag here.

## Test coverage gap (blocking)

The ticket says: *"add tests so this cannot regress."* As shipped, nothing in the test suite exercises
a lot count anywhere near the one that broke:

- `tests/test_money.py:13` — `test_allocate_sums_exactly` parametrizes `parts` at `3, 6, 7, 3`.
- `tests/test_rating.py:30-33` — `test_per_lot_split_is_exact_for_awkward_lot_counts` uses
  `(3, 7, 11, 13)`.
- `tests/test_api.py:46-54` — `test_quote_is_cent_exact` picks whatever policy is first in the seeded
  list; it isn't guaranteed to hit a large-lot building, and doesn't assert on lot count at all.

`LARGE_SCHEDULE` was 50, and the reported failure was 113 lots. None of the existing or added tests
put `parts` anywhere close to that range. Since the buggy branch is now deleted, these tests can't
*currently* regress against it — but that's precisely the danger: the original bug was introduced by
commit `ab3e6fd` ("Fast path for large lot schedules") without anyone adding a large-`parts` case, and
it went undetected by CI because every test used single-digit lot counts. Without a test asserting
`sum(allocate(...)) == total` for something like 100+ lots (ideally the literal 113-lot,
`$61,412.20` case from the ticket), a future "let's optimize for big plans" change could reintroduce
the exact same class of bug and the suite would stay green.

**Ask:** add at minimum one case to `tests/test_money.py:13`'s parametrize list with `parts` well above
50 (e.g. 113, 250), and ideally the literal Harbourview premium/lot count so the regression test reads
as a direct citation of the incident. This is a small addition and should not require touching
`rating.py` or any business logic.

## Not changed (confirmed correctly out of scope)

- No changes to `migrations/`.
- No dependency changes.
- No changes to renewal window, risk weights, or rating constants.
