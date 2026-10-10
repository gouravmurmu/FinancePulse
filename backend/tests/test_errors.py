from fastapi import APIRouter

from app.core.errors import AppError


def test_unknown_route_uses_error_envelope(make_client):
    res = make_client().get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_app_error_and_unhandled_errors(make_client):
    client = make_client()
    router = APIRouter()

    @router.get("/boom-app")
    def boom_app() -> None:
        raise AppError("rate_limited", "Slow down", 429, {"retry_after": 5})

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    client.app.include_router(router)

    res = client.get("/boom-app")
    assert res.status_code == 429
    assert res.json()["error"] == {
        "code": "rate_limited",
        "message": "Slow down",
        "details": {"retry_after": 5},
    }

    res = client.get("/boom")
    assert res.status_code == 500
    # Internal details must never leak to clients.
    assert "secret" not in res.text
    assert res.json()["error"]["code"] == "internal_error"


def test_cors_allows_configured_origin_only(make_client):
    client = make_client(CORS_ORIGINS="https://app.example.com")
    ok = client.options(
        "/api/v1/health",
        headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "https://app.example.com"
    bad = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
