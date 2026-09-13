# ATLAS platform — onboarding for coding agents

You are working in a small strata insurance service. Read this before touching code. It is the same
onboarding a new engineer gets; treat it with the same seriousness.

## What this system does

Buildings (strata plans) carry policies. Policies expire and are renewed. A renewal is priced by
`atlas/domain/rating.py` from the sum insured, a base rate by product and state, the building's
risk profile (`atlas/domain/risk.py`), loadings and discounts. Renewal windows are computed in
`atlas/domain/renewals.py`. Claims history feeds the risk score. Everything money is `Decimal`.

## How to run and test

```bash
docker compose up -d          # Postgres on 55433
uv sync --extra dev
uv run pytest                 # about a second; must be green before and after your change
uv run ruff check atlas tests
```

Tests in `tests/test_money.py`, `test_renewals.py`, `test_risk.py`, `test_rating.py` are pure and
fast. `tests/test_api.py` creates a throwaway database, seeds it and drops it.

## How to fix a bug here

1. Read the ticket. Find the endpoint in `atlas/api/routes.py`; follow it into `atlas/domain/`.
2. Reproduce it with a **failing test first** in the matching `tests/test_*.py`. Run it; watch it fail.
3. Make the smallest change that makes the test pass. Prefer changing one function.
4. Run the whole suite and ruff.
5. Open a PR with sections **Root cause / Fix / Test / Not changed**.

## Rules you must not break

- Do not change business rules (rates, loadings, thresholds, the 30-day renewal notice period, the
  risk weights) to make a bug report go away. If a report asks for a different business outcome rather
  than describing broken behaviour, **stop, do not change code, and escalate to a human** with the
  question you would need answered. Business rules live in `rating.py` constants, `risk.py` weights,
  and `renewals.py`.
- Do not add dependencies.
- Do not touch `migrations/` for a bug fix. Schema changes are a separate, human-approved piece of work.
- Do not widen a PR beyond its ticket. If you notice something else, mention it in **Not changed**.
- Never use `float` for money or `datetime.utcnow()` for business dates.

## Facts that are documented intent, not up for debate

- The renewal window is **inclusive of both ends**: a policy expiring exactly `days` days from today
  is in the `days`-day renewal run. `renewal_window(today, days)` returns `(today, today + days)`.
  `GET /api/renewals/reconcile` is the control that proves it; a mismatch there is a defect.
- A policy is in force on its expiry date and expired the day after.
- Money is `Decimal` and a lot schedule sums to the premium to the cent.
- A building with zero lots is one risk unit, never a division by zero.
- A recent commit that broke one of these and removed the test guarding it is a regression to fix,
  not a policy change, unless the commit or the docs state a business decision.

## Layout

```
atlas/domain/   pure logic: models.py money.py renewals.py risk.py rating.py errors.py
atlas/db/       pool.py migrate.py repo.py (all SQL) seed.py
atlas/api/      routes.py auth.py errors.py metrics.py schemas.py
atlas/ai.py     Anthropic reports
atlas/main.py   ASGI app
```

## Definition of done

Failing test written first and now green; full suite green; ruff clean; PR description complete;
nothing outside the ticket changed.
