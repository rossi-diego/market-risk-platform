#!/usr/bin/env python
"""Pre-promotion smoke test for the prod backend.

Runs three checks in order, short-circuiting on the first failure:
    1. `/api/v1/health` returns 200 on the target URL.
    2. Local `scripts/db_smoke.py` (DB reachability + seed row counts).
    3. `scripts/fetch_prices.py --dry-run` (yfinance reachable, records valid).

Usage:
    cd backend
    uv run --env-file .env python scripts/smoke_prod.py --url https://<render>.onrender.com

Exit codes:
    0 — all checks passed
    1 — at least one check failed (see stderr)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx

THIS_DIR = Path(__file__).resolve().parent


def _run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or THIS_DIR.parent, check=False)
    return result.returncode


def check_health(url: str, timeout: float = 30.0) -> int:
    target = url.rstrip("/") + "/api/v1/health"
    print(f"\nGET {target}")
    try:
        response = httpx.get(target, timeout=timeout)
    except httpx.HTTPError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    if response.status_code != 200:
        print(f"[FAIL] unexpected status {response.status_code}: {response.text}", file=sys.stderr)
        return 1
    body = response.json()
    print(f"[OK] {body}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-promotion smoke test")
    parser.add_argument("--url", required=True, help="Prod backend base URL")
    parser.add_argument(
        "--skip-db", action="store_true", help="Skip scripts/db_smoke.py (use for prod-only run)"
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip scripts/fetch_prices.py --dry-run (use when yfinance is flaky)",
    )
    args = parser.parse_args()

    rc = check_health(args.url)
    if rc != 0:
        return rc

    if not args.skip_db:
        rc = _run(["uv", "run", "python", "scripts/db_smoke.py"])
        if rc != 0:
            print("[FAIL] db_smoke exited non-zero", file=sys.stderr)
            return rc

    if not args.skip_fetch:
        rc = _run(["uv", "run", "python", "scripts/fetch_prices.py", "--dry-run"])
        if rc != 0:
            print("[FAIL] fetch_prices dry-run exited non-zero", file=sys.stderr)
            return rc

    print("\nAll prod smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
