"""Test fixtures.

Domain tests need nothing. API tests need Postgres: they create a throwaway database on the server
named by DB_HOST/DB_PORT/DB_USER/DB_PASSWORD (default: the docker-compose instance on 55433),
migrate it, seed a small portfolio, and drop it afterwards.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

os.environ.setdefault("DB_PORT", "55433")
os.environ.setdefault("DB_USER", "atlas")
os.environ.setdefault("DB_PASSWORD", "atlas")
os.environ["DB_NAME"] = f"atlas_test_{uuid.uuid4().hex[:8]}"
os.environ["BASIC_AUTH_USER"] = ""
os.environ["QUEUE_URL_PROD_ERRORS"] = ""
os.environ["EVENT_BUS"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

from atlas.domain.models import Building, Claim, Policy


@pytest.fixture
def building() -> Building:
    return Building(
        id=1,
        plan_number="SP 999001",
        name="Test Towers",
        suburb="Testville",
        state="NSW",
        postcode="2000",
        year_built=2005,
        floors=10,
        lots=40,
        construction_type="concrete",
        roof_type="metal",
        sprinklers=True,
        flood_zone="none",
        bushfire_bal="none",
        distance_to_coast_km=12.0,
        cladding_flag=False,
        last_inspection=date(2025, 6, 1),
    )


@pytest.fixture
def policy() -> Policy:
    return Policy(
        id=1,
        policy_number="ATL-1",
        building_id=1,
        broker_id=1,
        product="residential_strata",
        inception_date=date(2025, 10, 1),
        expiry_date=date(2026, 10, 1),
        sum_insured=Decimal("20000000.00"),
        base_premium=Decimal("47000.00"),
        status="active",
    )


def make_claim(
    i: int, loss: date, peril: str = "water_damage", incurred: str = "5000", status: str = "closed"
) -> Claim:
    return Claim(
        id=i,
        claim_number=f"CLM-{i}",
        policy_id=1,
        building_id=1,
        loss_date=loss,
        reported_date=loss,
        peril=peril,
        status=status,
        incurred=Decimal(incurred),
        paid=Decimal(incurred),
        description="test",
    )


@pytest.fixture(scope="session")
def db():
    import psycopg

    from atlas.db.migrate import migrate
    from atlas.db.pool import pool
    from atlas.db.seed import seed
    from atlas.settings import settings

    s = settings()
    migrate()
    seed(buildings=60, as_of=date(2026, 9, 13))
    yield s.db_name
    pool().close()
    with psycopg.connect(s.admin_dsn, autocommit=True) as c:
        c.execute(f'drop database "{s.db_name}" with (force)')


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from atlas.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def captured_errors(monkeypatch):
    """Collect error events instead of shipping them."""
    from atlas.api import errors as errors_mod

    events: list[dict] = []
    monkeypatch.setattr(errors_mod, "emit_error", events.append)
    return events
