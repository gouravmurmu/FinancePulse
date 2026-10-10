"""Verify Supabase access tokens and resolve the calling user.

The API trusts only the token's signature, expiry, audience and issuer. RLS
still protects direct database access; the API connects as the table owner, so
every user-data query here also filters on the verified user id.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import Settings
from app.core.errors import AppError

ASYMMETRIC_ALGS = ["ES256", "RS256", "EdDSA"]


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    # Keys are cached in-process; unknown key ids trigger one refetch.
    return PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


def _unauthorized(message: str = "Sign in to continue") -> AppError:
    return AppError("unauthorized", message, 401)


def verify_token(token: str, settings: Settings) -> uuid.UUID:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Your session is not valid. Sign in again.") from exc

    alg = header.get("alg")
    issuer = f"{settings.supabase_url}/auth/v1" if settings.supabase_url else None
    options: Any = {"require": ["exp", "sub"]}
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise _unauthorized("Your session is not valid. Sign in again.")
            key: Any = settings.supabase_jwt_secret
            algorithms = ["HS256"]
        elif alg in ASYMMETRIC_ALGS:
            if not settings.supabase_url:
                raise AppError("auth_not_configured", "Sign-in is not configured", 503)
            client = _jwks_client(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
            key = client.get_signing_key_from_jwt(token).key
            algorithms = [alg]
        else:
            raise _unauthorized("Your session is not valid. Sign in again.")
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.jwt_audience,
            issuer=issuer,
            options=options,
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Your session has expired. Sign in again.") from exc
    except jwt.PyJWKClientError as exc:
        raise AppError("auth_unavailable", "Could not check your session. Try again.", 503) from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Your session is not valid. Sign in again.") from exc

    if claims.get("role") != "authenticated":
        raise _unauthorized()
    try:
        return uuid.UUID(str(claims["sub"]))
    except ValueError as exc:
        raise _unauthorized() from exc
