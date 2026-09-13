"""Outbound signals: production error events to SQS and domain events to EventBridge.

Both are best-effort. A failure to emit never fails the request; it is logged instead.
"""
from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from functools import lru_cache

from .settings import settings

log = logging.getLogger(__name__)


@lru_cache
def _sqs():
    import boto3

    return boto3.client("sqs", region_name=settings().aws_region)


@lru_cache
def _events():
    import boto3

    return boto3.client("events", region_name=settings().aws_region)


def error_event(
    *,
    request_id: str,
    endpoint: str,
    method: str,
    exc: BaseException,
    kind: str,
    customer_impact: int,
    status_code: int,
    extra: dict | None = None,
) -> dict:
    ev = {
        "type": "error.raised",
        "service": settings().service_name,
        "environment": settings().environment,
        "ts": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "kind": kind,  # crash | business_rule
        "error_type": type(exc).__name__,
        "message": str(exc),
        "stack": "".join(traceback.format_exception(exc))[-6000:],
        "customer_impact": customer_impact,
        "signature": f"{endpoint}:{type(exc).__name__}",
        **(extra or {}),
    }
    return ev


def emit_error(ev: dict) -> None:
    log.error("production error", extra={"event": ev})
    url = settings().queue_url_prod_errors
    if not url:
        return
    try:
        _sqs().send_message(QueueUrl=url, MessageBody=json.dumps(ev, default=str))
    except Exception:
        log.exception("failed to send error event")
    bus = settings().event_bus
    if bus:
        try:
            _events().put_events(
                Entries=[{"Source": "atlas.platform", "DetailType": "error.raised", "EventBusName": bus, "Detail": json.dumps(ev, default=str)}]
            )
        except Exception:
            log.exception("failed to put error event")
