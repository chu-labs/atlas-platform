"""Tiny in-process counters exposed in Prometheus text format at /metrics."""

from __future__ import annotations

from collections import Counter

_requests: Counter = Counter()
_errors: Counter = Counter()


def observe(path: str, status: int) -> None:
    _requests[(path.split("?")[0], str(status))] += 1


def count_error(kind: str) -> None:
    _errors[kind] += 1


def render() -> str:
    lines = ["# TYPE atlas_http_requests_total counter"]
    for (path, status), n in sorted(_requests.items()):
        lines.append(f'atlas_http_requests_total{{path="{path}",status="{status}"}} {n}')
    lines.append("# TYPE atlas_errors_total counter")
    for kind, n in sorted(_errors.items()):
        lines.append(f'atlas_errors_total{{kind="{kind}"}} {n}')
    return "\n".join(lines) + "\n"
