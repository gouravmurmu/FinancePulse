"""Expensive endpoints are rate limited per client."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handlers
from app.core.rate_limit import WINDOW_SECONDS, limiter, rate_limit


def test_window_slides():
    assert limiter.hit("b", "ip", 2, now=0) is None
    assert limiter.hit("b", "ip", 2, now=1) is None
    wait = limiter.hit("b", "ip", 2, now=2)
    assert wait is not None and abs(wait - (WINDOW_SECONDS - 2)) < 1e-9
    # Other clients and buckets are independent.
    assert limiter.hit("b", "other", 2, now=2) is None
    assert limiter.hit("c", "ip", 2, now=2) is None
    # After the window the oldest hit expires.
    assert limiter.hit("b", "ip", 2, now=WINDOW_SECONDS + 0.5) is None


def test_429_with_retry_after_and_forwarded_ip():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/x", dependencies=[rate_limit("x", 2)])
    def x() -> dict[str, bool]:
        return {"ok": True}

    c = TestClient(app)
    a = {"x-forwarded-for": "1.1.1.1, 10.0.0.1"}
    assert c.get("/x", headers=a).status_code == 200
    assert c.get("/x", headers=a).status_code == 200
    r = c.get("/x", headers=a)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert c.get("/x", headers={"x-forwarded-for": "2.2.2.2"}).status_code == 200
