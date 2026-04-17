"""Diagnostic — inspect what JWT algorithm Supabase is issuing.

Creates a disposable auth user, exchanges credentials for a token,
decodes the header + payload WITHOUT verification (so any alg works),
prints the relevant fields, then deletes the user.

Run:
    cd backend && uv run --env-file .env python scripts/diag_jwt.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
from uuid import uuid4

import httpx


def b64d(s: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode())


def main() -> int:
    try:
        url = os.environ["SUPABASE_URL"].rstrip("/")
        admin = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        anon = os.environ["SUPABASE_ANON_KEY"]
    except KeyError as e:
        print(f"Missing env var: {e}")
        return 1

    email = f"diag-{uuid4().hex[:8]}@example.com"
    password = uuid4().hex + "Aa!1"

    # 1. Create user
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
        print(f"Admin user creation failed: {r.status_code}")
        print(r.text)
        return 2
    user_id = r.json()["id"]

    try:
        # 2. Get token via password grant
        r = httpx.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=30.0,
        )
        if r.status_code >= 400:
            print(f"Token grant failed: {r.status_code}")
            print(r.text)
            return 3

        tok = r.json()["access_token"]

        # 3. Decode header + payload (unverified)
        header_b64, payload_b64, _sig = tok.split(".")
        header = b64d(header_b64)
        payload = b64d(payload_b64)

        print("=" * 60)
        print("JWT HEADER:")
        print(json.dumps(header, indent=2))
        print()
        print("JWT PAYLOAD — relevant claims:")
        print(f"  aud        = {payload.get('aud')}")
        print(f"  iss        = {payload.get('iss')}")
        print(f"  role       = {payload.get('role')}")
        print(f"  sub prefix = {str(payload.get('sub', ''))[:8]}...")
        print(f"  exp        = {payload.get('exp')}")
        print()
        print("All payload keys:", list(payload.keys()))
        print("=" * 60)

        alg = header.get("alg")
        print(f"\nALG = {alg}")
        if alg == "HS256":
            print("→ Backend config is compatible (HS256). Check SUPABASE_JWT_SECRET value.")
        elif alg in ("ES256", "RS256"):
            print(f"→ Backend uses HS256 only — must add {alg} support.")
        else:
            print(f"→ Unexpected algorithm: {alg}")

        # 4. Also check if SUPABASE_JWT_SECRET looks like HS256 shared secret vs asymmetric key
        secret = os.environ.get("SUPABASE_JWT_SECRET", "")
        print("\nSUPABASE_JWT_SECRET inspection:")
        print(f"  length: {len(secret)} chars")
        print(f"  starts with: {secret[:20]!r}...")
        if secret.startswith("-----BEGIN"):
            print("  → looks like a PEM key (asymmetric)")
        elif secret.startswith("{"):
            print("  → looks like a JWK JSON object")
        elif len(secret) >= 32 and all(c.isalnum() or c in "-_=" for c in secret):
            print("  → looks like an HS256 shared secret (base64-ish string)")
        else:
            print("  → unclear format — paste first 30 chars to Cowork if unsure")

        return 0
    finally:
        httpx.delete(
            f"{url}/auth/v1/admin/users/{user_id}",
            headers={"apikey": admin, "Authorization": f"Bearer {admin}"},
            timeout=30.0,
        )
        print("\n(test user deleted)")


if __name__ == "__main__":
    sys.exit(main())
