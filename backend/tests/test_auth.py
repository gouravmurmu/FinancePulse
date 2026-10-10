"""Supabase access-token verification."""

import time
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import auth
from app.core.config import Settings
from app.core.errors import AppError

USER = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
URL = "https://example.supabase.co"
SECRET = "test-secret-with-at-least-32-bytes-long!"  # noqa: S105 (test-only key)


def claims(**over):
    base = {
        "sub": str(USER),
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{URL}/auth/v1",
        "exp": int(time.time()) + 600,
    }
    base.update(over)
    return base


def settings(**over):
    return Settings(supabase_url=URL, supabase_jwt_secret=SECRET, **over)


def test_hs256_token_resolves_user():
    token = jwt.encode(claims(), SECRET, algorithm="HS256")
    assert auth.verify_token(token, settings()) == USER


@pytest.mark.parametrize(
    "bad",
    [
        {"exp": int(time.time()) - 10},
        {"aud": "other"},
        {"iss": "https://evil.example/auth/v1"},
        {"role": "anon"},
    ],
)
def test_invalid_claims_are_rejected(bad):
    token = jwt.encode(claims(**bad), SECRET, algorithm="HS256")
    with pytest.raises(AppError) as e:
        auth.verify_token(token, settings())
    assert e.value.status_code == 401


def test_wrong_secret_is_rejected():
    token = jwt.encode(claims(), "x" * 40, algorithm="HS256")
    with pytest.raises(AppError):
        auth.verify_token(token, settings())


def test_unsigned_token_is_rejected():
    token = jwt.encode(claims(), None, algorithm="none")
    with pytest.raises(AppError):
        auth.verify_token(token, settings())


def test_es256_token_is_checked_against_jwks(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(claims(), key, algorithm="ES256", headers={"kid": "k1"})
    seen = {}

    def fake_client(url):
        seen["url"] = url
        return SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())
        )

    monkeypatch.setattr(auth, "_jwks_client", fake_client)
    assert auth.verify_token(token, settings()) == USER
    assert seen["url"] == f"{URL}/auth/v1/.well-known/jwks.json"

    other = ec.generate_private_key(ec.SECP256R1())
    forged = jwt.encode(claims(), other, algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(AppError):
        auth.verify_token(forged, settings())


def test_missing_header_is_401(make_client):
    res = make_client().get("/api/v1/portfolios")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
