"""End-to-end smoke test for the risk endpoints.

Creates a disposable Supabase auth user, exchanges credentials for a JWT,
calls POST /api/v1/risk/stress/historical against a local uvicorn, prints
the result, then deletes the test user.

Prereqs:
- `uvicorn app.main:app --reload` running on localhost:8000
- backend/.env has SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

Run:
    cd backend && uv run --env-file .env python scripts/smoke_risk.py
"""

from __future__ import annotations

import json
import os
import sys
from uuid import uuid4

import httpx

API = "http://localhost:8000/api/v1"

# Canonical portfolio from Phase 6 handoff:
# 1000 ton soja long, CBOT=1000 USc/bu, FX=5, basis=0.5
BODY = {
    "exposure_tons_by_commodity": {
        "soja": {"cbot": "1000", "basis": "1000", "fx": "1000"},
    },
    "prices_current": {
        "cbot_soja": "1000",
        "fx": "5",
        "basis_soja": "0.5",
    },
}


def main() -> int:
    try:
        url = os.environ["SUPABASE_URL"].rstrip("/")
        admin = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        anon = os.environ["SUPABASE_ANON_KEY"]
    except KeyError as e:
        print(f"Missing env var: {e}")
        print("Run with `uv run --env-file .env python scripts/smoke_risk.py`")
        return 1

    # 1) Create disposable user
    email = f"smoke-{uuid4().hex[:8]}@example.com"
    password = uuid4().hex + "Aa!1"
    print(f"[1/4] Creating test user {email}...")
    r = httpx.post(
        f"{url}/auth/v1/admin/users",
        headers={
            "apikey": admin,
            "Authorization": f"Bearer {admin}",
            "Content-Type": "application/json",
        },
        json={"email": email, "password": password, "email_confirm": True},
        timeout=30.0,
    )
    if r.status_code >= 400:
        print(f"  FAIL: {r.status_code} {r.text}")
        return 2
    user_id = r.json()["id"]
    print("       user_id:", user_id)

    try:
        # 2) Get JWT via password grant
        print("[2/4] Requesting JWT...")
        r = httpx.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=30.0,
        )
        r.raise_for_status()
        jwt = r.json()["access_token"]
        print("       got JWT:", jwt[:40], "...")

        # 3) Hit the endpoint
        print("[3/4] POST /risk/stress/historical ...")
        try:
            r = httpx.post(
                f"{API}/risk/stress/historical",
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type": "application/json",
                },
                json=BODY,
                timeout=30.0,
            )
        except httpx.ConnectError:
            print("       FAIL: could not connect to http://localhost:8000")
            print(
                "       Is uvicorn running? "
                "`uv run --env-file .env uvicorn app.main:app --reload`"
            )
            return 3

        print(f"       HTTP {r.status_code}")
        if r.status_code >= 400:
            print("       body:", r.text)
            return 4

        print()
        print("=" * 70)
        print("STRESS RESULTS (4 scenarios — look for 2008 GFC ≈ ±95 BRL)")
        print("=" * 70)
        try:
            data = r.json()
            print(json.dumps(data, indent=2))
        except Exception:
            print(r.text)
        print("=" * 70)
        return 0
    finally:
        # 4) Teardown
        print("\n[4/4] Deleting test user...")
        httpx.delete(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": admin, "Authorization": f"Bearer {admin}"},
            timeout=30.0,
        )
        print("       done.")


if __name__ == "__main__":
    sys.exit(main())
