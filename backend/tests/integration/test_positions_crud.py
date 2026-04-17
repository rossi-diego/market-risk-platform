"""Integration tests for the CRUD surface.

These tests require live Supabase (service-role key for admin user creation) and
are gated by `--run-integration`. The flow:
  1. Create a disposable Supabase auth user.
  2. Exchange that user's creds for a JWT via GoTrue password grant.
  3. Hit the FastAPI app in-process via httpx ASGITransport.
  4. Teardown deletes the user.

If `SUPABASE_URL` still points at `https://example.supabase.co` we skip early.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import httpx
import pytest

from app.main import app


def _env_ready() -> bool:
    url = os.environ.get("SUPABASE_URL", "")
    return url.startswith("https://") and "example.supabase.co" not in url


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def supabase_admin_headers() -> dict[str, str]:
    if not _env_ready():
        pytest.skip("SUPABASE_URL not configured for integration tests")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


@pytest.fixture()
def test_user_token(
    supabase_admin_headers: dict[str, str],
) -> Iterator[tuple[str, str]]:
    """Provision a one-off auth user and return (user_id, jwt). Delete on teardown."""
    if not _env_ready():
        pytest.skip("SUPABASE_URL not configured for integration tests")
    base = os.environ["SUPABASE_URL"].rstrip("/")
    email = f"cc-phase5-{uuid4().hex[:10]}@example.com"
    password = uuid4().hex + "Aa!1"

    # 1. admin create
    r = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=supabase_admin_headers,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=30.0,
    )
    r.raise_for_status()
    user_id: str = r.json()["id"]

    try:
        # 2. password grant → JWT
        anon = os.environ["SUPABASE_ANON_KEY"]
        token_resp = httpx.post(
            f"{base}/auth/v1/token?grant_type=password",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=30.0,
        )
        token_resp.raise_for_status()
        access_token: str = token_resp.json()["access_token"]
        yield user_id, access_token
    finally:
        # teardown
        httpx.delete(
            f"{base}/auth/v1/admin/users/{user_id}",
            headers=supabase_admin_headers,
            timeout=30.0,
        )


@pytest.fixture()
async def client(test_user_token: tuple[str, str]) -> AsyncIterator[httpx.AsyncClient]:
    _, token = test_user_token
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c


FRAME_BODY = {
    "commodity": "soja",
    "side": "sell",
    "quantity_tons": "1000",
    "delivery_start": "2026-05-01",
    "delivery_end": "2026-07-31",
    "counterparty": "CC test",
}


async def test_create_physical_frame(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/physical/frames", json=FRAME_BODY)
    assert r.status_code == 201, r.text
    frame_id = r.json()["id"]

    listing = await client.get("/api/v1/physical/frames")
    assert listing.status_code == 200
    assert any(f["id"] == frame_id for f in listing.json())


async def test_create_fixation_updates_status(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/physical/frames", json=FRAME_BODY)
    frame_id = r.json()["id"]

    fix = await client.post(
        f"/api/v1/physical/frames/{frame_id}/fixations",
        json={
            "fixation_mode": "flat",
            "quantity_tons": "500",
            "fixation_date": "2026-04-15",
            "cbot_fixed": "1420",
            "basis_fixed": "0.5",
            "fx_fixed": "5.0",
        },
    )
    assert fix.status_code == 201, fix.text
    detail = (await client.get(f"/api/v1/physical/frames/{frame_id}")).json()
    assert detail["status"] == "partial"


async def test_create_full_fixation_closes_frame(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/physical/frames", json=FRAME_BODY)
    frame_id = r.json()["id"]
    fix = await client.post(
        f"/api/v1/physical/frames/{frame_id}/fixations",
        json={
            "fixation_mode": "flat",
            "quantity_tons": "1000",
            "fixation_date": "2026-04-15",
            "cbot_fixed": "1420",
            "basis_fixed": "0.5",
            "fx_fixed": "5.0",
        },
    )
    assert fix.status_code == 201
    detail = (await client.get(f"/api/v1/physical/frames/{frame_id}")).json()
    assert detail["status"] == "closed"


async def test_fixation_over_lock_returns_409(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/physical/frames", json=FRAME_BODY)
    frame_id = r.json()["id"]
    ok = await client.post(
        f"/api/v1/physical/frames/{frame_id}/fixations",
        json={
            "fixation_mode": "cbot",
            "quantity_tons": "600",
            "fixation_date": "2026-04-15",
            "cbot_fixed": "1420",
        },
    )
    assert ok.status_code == 201
    over = await client.post(
        f"/api/v1/physical/frames/{frame_id}/fixations",
        json={
            "fixation_mode": "cbot",
            "quantity_tons": "500",
            "fixation_date": "2026-04-16",
            "cbot_fixed": "1425",
        },
    )
    assert over.status_code == 409
    body = over.json()["detail"]
    assert body["title"] == "over-locked leg"
    assert body["leg"] == "cbot"
    assert body["remaining_tons"] == "400.0000"


async def test_cbot_option_requires_fields(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/cbot",
        json={
            "commodity": "soja",
            "instrument": "european_option",
            "side": "buy",
            "contract": "ZSK26",
            "quantity_contracts": "1",
            "trade_date": "2026-04-15",
            "trade_price": "25",
            "maturity_date": "2026-05-15",
        },
    )
    assert r.status_code == 422


async def test_cbot_barrier_requires_fields(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/cbot",
        json={
            "commodity": "soja",
            "instrument": "barrier_option",
            "side": "buy",
            "contract": "ZSK26",
            "quantity_contracts": "1",
            "trade_date": "2026-04-15",
            "trade_price": "25",
            "maturity_date": "2026-05-15",
            "option_type": "call",
            "strike": "1450",
        },
    )
    assert r.status_code == 422
