# ATLAS platform

A small, real strata insurance service: buildings, lots, policies, claims, renewals, a building
risk score, a premium rating engine, and AI-written underwriting reports. FastAPI on Postgres.

It is the system under test for the ATLAS Agentic SDLC Demo Lab. Everything in it is synthetic:
plan numbers are in the fictional `SP 9xxxxx` range, building and broker names are generated,
and no record corresponds to a real policy, person or place. The domain shape is inspired by an
internal prototype; no code or data was taken from it.

## Run it locally

```bash
docker compose up -d                 # Postgres on :55433
cp .env.example .env
uv sync --extra dev
uv run python -m atlas.db seed       # migrate + 2,500 synthetic buildings
uv run uvicorn atlas.main:app --reload
open http://localhost:8000/docs
```

## Endpoints

| Method | Path | What |
|---|---|---|
| GET | `/health`, `/metrics` | Liveness and Prometheus counters (unauthenticated) |
| GET | `/api/policies?due_within_days=30` | Policies due for renewal in an inclusive window |
| GET | `/api/policies/{number}` | One policy with its building |
| POST | `/api/policies/{number}/quote` | Renewal premium quote, cent-exact per lot |
| GET | `/api/policies/{number}/claims` | Claims on a policy |
| GET | `/api/buildings`, `/api/buildings/{id}` | Buildings |
| GET | `/api/buildings/{id}/risk` | Five-pillar risk profile, 0 (best) to 100 |
| GET | `/api/buildings/{id}/claims`, `/policies` | Claims history and policy history |
| GET | `/api/stats` | Portfolio summary |
| POST | `/api/ai/building-report/{id}` | AI building risk report |
| POST | `/api/ai/underwriting-advice/{number}` | AI renewal recommendation |
| POST | `/api/ai/claims-summary/{id}` | AI claims history summary |

Every route except `/health` and `/metrics` requires basic auth when `BASIC_AUTH_USER` is set.

## How errors leave the building

Every unhandled exception and every `BusinessRuleViolation` becomes one structured JSON log line
and one message on the production error queue (`QUEUE_URL_PROD_ERRORS`), carrying the request ID,
endpoint, stack trace, a signature for deduplication, and a synthetic customer impact count. See
`atlas/api/errors.py` and `atlas/events.py`.

## Layout

```
atlas/domain/    pure business logic: models, money, renewals, risk, rating (no I/O)
atlas/db/        pool, migrations, repositories, seeder
atlas/api/       routes, auth, error pipeline, metrics, schemas
atlas/ai.py      Anthropic-backed reports
migrations/      numbered SQL, applied at startup
tests/           pytest; domain tests are pure, API tests use a throwaway database
```

## Deploy

`main` deploys to production through GitHub Actions (`.github/workflows/deploy.yml`): tests, an
arm64 image to ECR, then an ECS rollout gated by the `production` environment's required reviewer.
