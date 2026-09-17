"""Turn every unhandled exception and every business-rule violation into a structured error event."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..domain.errors import BusinessRuleViolation
from ..events import emit_error, error_event
from ..settings import settings
from . import metrics

log = logging.getLogger(__name__)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            return _handle(request, exc)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["x-request-id"] = rid
        metrics.observe(request.url.path, response.status_code)
        if elapsed_ms > settings().slow_request_ms and request.url.path.startswith("/api/"):
            _slow(request, elapsed_ms)
        return response

    @app.exception_handler(BusinessRuleViolation)
    async def business_rule(request: Request, exc: BusinessRuleViolation):
        return _handle(request, exc)


def _handle(request: Request, exc: BaseException) -> JSONResponse:
    rid = getattr(request.state, "request_id", "unknown")
    endpoint = request.scope.get("route").path if request.scope.get("route") else request.url.path
    if isinstance(exc, BusinessRuleViolation):
        status, kind, impact = 422, "business_rule", exc.customer_impact
        body = {"error": "business_rule_violation", "rule": exc.rule, "detail": exc.detail, "request_id": rid}
    else:
        status, kind, impact = 500, "crash", _impact(request)
        body = {"error": "internal_error", "request_id": rid}
    ev = error_event(
        request_id=rid,
        endpoint=endpoint,
        method=request.method,
        exc=exc,
        kind=kind,
        customer_impact=impact,
        status_code=status,
        extra={
            "path": str(request.url.path),
            "query": str(request.url.query),
            "path_params": dict(request.path_params),
        },
    )
    emit_error(ev)
    metrics.observe(request.url.path, status)
    metrics.count_error(kind)
    return JSONResponse(body, status_code=status, headers={"x-request-id": rid})


class SlowRequest(Exception):
    pass


def _slow(request: Request, elapsed_ms: float) -> None:
    rid = getattr(request.state, "request_id", "unknown")
    endpoint = request.scope.get("route").path if request.scope.get("route") else request.url.path
    exc = SlowRequest(
        f"{request.method} {endpoint} took {elapsed_ms:.0f} ms (threshold {settings().slow_request_ms} ms)"
    )
    ev = error_event(
        request_id=rid,
        endpoint=endpoint,
        method=request.method,
        exc=exc,
        kind="performance",
        customer_impact=_impact(request),
        status_code=200,
        extra={
            "path": str(request.url.path),
            "query": str(request.url.query),
            "elapsed_ms": round(elapsed_ms),
        },
    )
    ev["stack"] = ""  # nothing raised; the signature and timing are the evidence
    emit_error(ev)
    metrics.count_error("performance")


def _impact(request: Request) -> int:
    """Synthetic customer impact: how many policyholders a failure on this path touches."""
    p = request.url.path
    if p.startswith("/api/policies") and "due" in request.url.query:
        return 40
    if p.startswith("/api/buildings"):
        return 12
    return 1
