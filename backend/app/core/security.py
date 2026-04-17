"""Supabase JWT validation for FastAPI.

The backend uses ``SUPABASE_SERVICE_ROLE_KEY`` for its DB connection and
enforces per-user isolation at the application layer by filtering queries on
``user_id`` (derived from the JWT ``sub`` claim). Supabase RLS policies remain
enabled as defense in depth, but the service-role key bypasses them by design.

Supports both signing algorithms Supabase may issue:

- **HS256** (legacy shared secret) — verified with ``settings.SUPABASE_JWT_SECRET``.
- **ES256** (modern asymmetric, default on projects created in 2025+) — public
  keys fetched from ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json`` and
  matched by the token's ``kid`` header. Cached in-process; refreshed lazily
  when an unknown ``kid`` is seen (key rotation).

The algorithm is chosen per-token from the header's ``alg`` field. Any other
algorithm is rejected with 401.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings


class UserPrincipal(BaseModel):
    id: UUID
    email: str
    role: str = "authenticated"


def _problem(title: str, detail: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={
            "type": "about:blank",
            "title": title,
            "status": http_status,
            "detail": detail,
        },
    )


# --------------------------------------------------------------------------- #
# JWKS cache (ES256 path)
# --------------------------------------------------------------------------- #

_JWKS_URL = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
_jwks_cache: list[dict[str, Any]] = []
_jwks_lock = asyncio.Lock()


async def _refresh_jwks() -> None:
    """Fetch fresh JWKS from Supabase and replace the cache in place."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(_JWKS_URL)
        resp.raise_for_status()
        data = resp.json()
    _jwks_cache.clear()
    _jwks_cache.extend(data.get("keys", []))


async def _get_jwk(kid: str) -> dict[str, Any] | None:
    """Return the JWK dict for a given key id, refreshing the cache once if needed."""
    for key in _jwks_cache:
        if key.get("kid") == kid:
            return key
    async with _jwks_lock:
        # Double-check in case another coroutine refreshed while we waited.
        for key in _jwks_cache:
            if key.get("kid") == kid:
                return key
        await _refresh_jwks()
    for key in _jwks_cache:
        if key.get("kid") == kid:
            return key
    return None


# --------------------------------------------------------------------------- #
# Public dependency
# --------------------------------------------------------------------------- #


async def get_current_user(authorization: str = Header(...)) -> UserPrincipal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _problem(
            "missing or malformed bearer token",
            "Authorization header must be 'Bearer <jwt>'",
            status.HTTP_401_UNAUTHORIZED,
        )
    token = authorization.split(" ", 1)[1].strip()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _problem(
            "invalid token",
            f"Could not parse JWT header: {exc}",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc

    alg = header.get("alg")

    try:
        if alg == "HS256":
            claims: dict[str, Any] = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        elif alg == "ES256":
            kid = header.get("kid")
            if not kid:
                raise _problem(
                    "invalid token",
                    "ES256 JWT header missing 'kid'",
                    status.HTTP_401_UNAUTHORIZED,
                )
            jwk_dict = await _get_jwk(kid)
            if jwk_dict is None:
                raise _problem(
                    "invalid token",
                    f"No JWK found for kid '{kid}' in Supabase JWKS",
                    status.HTTP_401_UNAUTHORIZED,
                )
            claims = jwt.decode(
                token,
                jwk_dict,
                algorithms=["ES256"],
                audience="authenticated",
            )
        else:
            raise _problem(
                "invalid token",
                f"Unsupported JWT alg '{alg}' (expected HS256 or ES256)",
                status.HTTP_401_UNAUTHORIZED,
            )
    except HTTPException:
        raise
    except JWTError as exc:
        raise _problem(
            "invalid token",
            f"JWT decode failed: {exc}",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc

    sub = claims.get("sub")
    email = claims.get("email", "")
    role = claims.get("role", "authenticated")
    if not sub:
        raise _problem(
            "invalid token",
            "JWT missing 'sub' claim",
            status.HTTP_401_UNAUTHORIZED,
        )
    return UserPrincipal(id=UUID(str(sub)), email=email, role=role)
