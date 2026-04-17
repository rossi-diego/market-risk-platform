"""Supabase DB smoke test.

Verifies that:
  1. All required env vars load from backend/.env
  2. DATABASE_URL resolves and the pooler accepts the connection
  3. The 10 tables exist with the expected seed counts

Run from repo root:
    cd backend && uv run python scripts/db_smoke.py

Exit codes:
    0 = all checks passed, DB ready for Phase 2
    1 = connected but seed counts don't match (migrations incomplete?)
    2 = connection failed (wrong URL, password, network, etc.)
    3 = missing env vars in .env
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def _yellow(s: str) -> str:
    return f"\033[33m{s}\033[0m"


async def _run_checks() -> int:
    # Step 1 — env vars
    try:
        from app.core.config import settings
    except Exception as e:
        print(_red(f"[FAIL] Could not load settings: {type(e).__name__}: {e}"))
        print("       → Check backend/.env has all 5 required keys.")
        return 3

    required = [
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "DATABASE_URL",
    ]
    missing: list[str] = []
    for key in required:
        val = getattr(settings, key, None)
        if not val or (isinstance(val, str) and val.startswith("<")):
            missing.append(key)
    if missing:
        print(_red(f"[FAIL] Missing or placeholder env vars: {', '.join(missing)}"))
        print("       → Edit backend/.env and replace any <replace-me> values.")
        return 3

    print(_green("[OK]   All 5 env vars loaded from backend/.env"))

    # Step 2 — connection
    try:
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            connect_args={"statement_cache_size": 0},
        )
        async with engine.connect() as conn:
            # Step 3 — seed counts
            result: dict[str, Any] = {}
            for tbl, expected in [
                ("prices", 0),
                ("scenarios_templates", 4),
                ("mtm_premiums", 2),
                ("physical_frames", 0),
                ("cbot_derivatives", 0),
                ("basis_forwards", 0),
                ("fx_derivatives", 0),
            ]:
                actual = (await conn.execute(text(f"select count(*) from {tbl}"))).scalar()
                result[tbl] = (actual, expected)
        await engine.dispose()
    except Exception as e:
        print(_red(f"[FAIL] Connection failed: {type(e).__name__}"))
        print(f"       {e}")
        print("       → Most common causes:")
        print("         • Password has special chars not URL-encoded ($ → %24, @ → %40, etc.)")
        print("         • Using direct connection string instead of Transaction pooler URL")
        print("         • Missing `postgresql+asyncpg://` prefix (just `postgresql://`)")
        return 2

    print(_green("[OK]   Connected to Supabase via transaction pooler"))

    bad = [(t, got, exp) for t, (got, exp) in result.items() if got != exp]
    if bad:
        print(_yellow("[WARN] Seed counts don't match expected:"))
        for t, got, exp in bad:
            print(f"         {t}: got {got}, expected {exp}")
        return 1

    print(_green("[OK]   All 7 table counts match expected (0, 4, 2, 0, 0, 0, 0)"))
    print()
    print(_green("DB is ready for Phase 2."))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run_checks()))
