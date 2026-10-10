import os

import pytest


def test_health_without_database(make_client):
    client = make_client()
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == {"status": "not_configured", "latency_ms": None}
    assert "server_time" in body


def test_health_reports_unreachable_database_as_degraded(make_client):
    # Port 1 on localhost refuses connections immediately.
    client = make_client(DATABASE_URL="postgresql://u:p@127.0.0.1:1/db")
    body = client.get("/api/v1/health").json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "unavailable"


@pytest.mark.db
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_health_with_database(make_client):
    client = make_client(DATABASE_URL=os.environ["TEST_DATABASE_URL"])
    body = client.get("/api/v1/health").json()
    assert body["database"]["status"] == "ok"
    assert body["database"]["latency_ms"] is not None


def test_request_id_header(make_client):
    res = make_client().get("/api/v1/health", headers={"x-request-id": "abc123"})
    assert res.headers["x-request-id"] == "abc123"
