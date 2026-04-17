"""Supabase JWT validation for FastAPI.

The backend uses `SUPABASE_SERVICE_ROLE_KEY` for its DB connection and enforces
per-user isolation at the application layer by filtering queries on `user_id`
(derived from the JWT `sub` claim). Supabase RLS policies remain enabled as
defense in depth, but the service-role key bypasses them by design.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

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


async def get_current_user(authorization: str = Header(...)) -> UserPrincipal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _problem(
            "missing or malformed bearer token",
            "Authorization header must be 'Bearer <jwt>'",
            status.HTTP_401_UNAUTHORIZED,
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
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
