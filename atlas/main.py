"""ASGI entry point: `uvicorn atlas.main:app`."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from . import __version__
from .api import errors, metrics
from .api.auth import BasicAuthMiddleware
from .api.routes import router
from .logging_setup import configure
from .settings import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure()
    from .db.migrate import migrate

    try:
        applied = migrate()
        log.info("startup", extra={"version": __version__, "migrations_applied": applied})
    except Exception:
        log.exception("migration failed at startup")
    yield


app = FastAPI(title="ATLAS platform", version=__version__, lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)
errors.install(app)
app.include_router(router)


@app.get("/health")
def health():
    from .db.pool import conn

    db_ok = True
    try:
        with conn() as c:
            c.execute("select 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "service": settings().service_name, "version": __version__, "db": db_ok}


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus():
    return metrics.render()
