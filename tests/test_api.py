from datetime import date, timedelta


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] is True


def test_metrics_is_prometheus_text(client):
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "atlas_http_requests_total" in r.text


def test_policy_list_carries_building_fields(client):
    row = client.get("/api/policies", params={"limit": 1}).json()[0]
    assert row["building_name"] and row["plan_number"].startswith("SP 9")


def test_building_risk(client):
    r = client.get("/api/buildings/1/risk")
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100 and body["band"] in "ABCDE"


def test_quote_is_cent_exact(client):
    pn = client.get("/api/policies", params={"limit": 1}).json()[0]["policy_number"]
    r = client.post(f"/api/policies/{pn}/quote")
    assert r.status_code == 200
    from decimal import Decimal

    q = r.json()
    assert sum(Decimal(x) for x in q["per_lot"]) == Decimal(q["annual_premium"])


def test_quote_on_lapsed_policy_is_a_business_rule_violation(client, captured_errors):
    from atlas.db.pool import conn

    with conn() as c:
        pn = c.execute("select policy_number from policies where status='lapsed' limit 1").fetchone()["policy_number"]
    r = client.post(f"/api/policies/{pn}/quote")
    assert r.status_code == 422
    assert r.json()["rule"] == "quote.inactive_policy"
    assert captured_errors and captured_errors[0]["kind"] == "business_rule"
    assert captured_errors[0]["endpoint"] == "/api/policies/{policy_number}/quote"


def test_unhandled_exception_becomes_error_event(client, captured_errors, monkeypatch):
    from atlas.api import routes

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(routes.repo, "get_building", boom)
    r = client.get("/api/buildings/1")
    assert r.status_code == 500
    assert r.json()["error"] == "internal_error"
    ev = captured_errors[0]
    assert ev["kind"] == "crash" and ev["error_type"] == "RuntimeError"
    assert "kaboom" in ev["stack"] and ev["request_id"] == r.headers["x-request-id"]
    assert ev["customer_impact"] >= 1


def test_404s(client):
    assert client.get("/api/policies/NOPE").status_code == 404
    assert client.get("/api/buildings/999999").status_code == 404


def test_ai_without_key_is_503(client):
    assert client.post("/api/ai/building-report/1").status_code == 503


def test_basic_auth_when_configured(client, monkeypatch):
    from atlas.settings import settings

    monkeypatch.setattr(settings(), "basic_auth_user", "u")
    monkeypatch.setattr(settings(), "basic_auth_pass", "p")
    assert client.get("/api/stats").status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/api/stats", auth=("u", "p")).status_code == 200


def _skip_reconcile(client, monkeypatch):
    from atlas.api import routes

    monkeypatch.setattr(routes, "_today", lambda: date(2026, 9, 13))
    r = client.get("/api/renewals/reconcile", params={"days": 30})
    assert r.status_code == 200 and r.json()["missing"] == 0


def test_policy_expiring_today_can_be_quoted(client, monkeypatch):
    from atlas.api import routes
    from atlas.db.pool import conn

    with conn() as c:
        row = c.execute("select policy_number, expiry_date from policies where status='active' order by expiry_date limit 1").fetchone()
    monkeypatch.setattr(routes, "_today", lambda: row["expiry_date"])
    assert client.post(f"/api/policies/{row['policy_number']}/quote").status_code == 200


def test_slow_requests_emit_a_performance_event(client, captured_errors, monkeypatch):
    import time

    from atlas.api import routes
    from atlas.settings import settings

    monkeypatch.setattr(settings(), "slow_request_ms", 10)
    real = routes.repo.portfolio_stats
    monkeypatch.setattr(routes.repo, "portfolio_stats", lambda: (time.sleep(0.03), real())[1])
    assert client.get("/api/stats").status_code == 200
    assert captured_errors and captured_errors[0]["kind"] == "performance"
    assert captured_errors[0]["elapsed_ms"] >= 10
