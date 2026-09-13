# Contributing to ATLAS

These conventions apply to every contributor, human or agent.

## Branches and pull requests

- Branch from `main`: `fix/ATLAS-123-short-description` or `feat/ATLAS-123-short-description`.
- One ticket per PR. Do not bundle unrelated changes; a reviewer will send it back.
- The PR description has four sections: **Root cause**, **Fix**, **Test**, **Not changed** (what you
  deliberately left alone and why).
- `main` is protected: CI must pass and one human approval is required. Agents cannot approve.

## Tests

- Run everything with `uv run pytest`. It needs the docker-compose Postgres.
- A bug fix starts with a failing test that reproduces the bug. Commit the test, then the fix.
- Domain logic lives in `atlas/domain/` and is tested without a database. If you need the database to
  test a calculation, the calculation is in the wrong place.
- Money is `Decimal`. A test that compares money with `float` is wrong.

## Style

- `ruff check` must pass. Line length 110. Type hints on public functions.
- Dates: business dates are `date` in `Australia/Sydney`; instants are timezone-aware `datetime`.
- Errors: raise `BusinessRuleViolation` for rule breaches; let real bugs raise. Both are shipped
  as error events automatically.

## Definition of done

1. Failing test written first, now passing.
2. Full suite green locally.
3. PR description complete, including what you did not change.
4. Ticket moved to *In Review*.
