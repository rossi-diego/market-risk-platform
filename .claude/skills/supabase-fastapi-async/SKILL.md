---
name: supabase-fastapi-async
description: >
  Production patterns for integrating FastAPI (async) with Supabase in the
  commodity-risk-dashboard project. Use this skill whenever writing or reviewing
  backend code that touches: Supabase client setup, async database access,
  Row Level Security (RLS), Storage bucket access for file uploads,
  Supabase Auth JWT validation in FastAPI, upsert patterns, migration management,
  or any question about how the FastAPI backend connects to Supabase.
  Also trigger when the user asks about environment variables for Supabase,
  the difference between anon key and service role key, or how to test
  Supabase-backed endpoints.
---

# Supabase + FastAPI Async Patterns

Canonical integration patterns for the commodity-risk-dashboard backend.
Supabase provides: PostgreSQL (hosted), Auth (JWT), Storage (file uploads), Realtime.
FastAPI handles: business logic, risk calculations, price fetching, validation.

---

## Environment Variables

```bash
# .env (backend) — never commit, always .env.example
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...          # safe for frontend / public reads
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # backend ONLY — bypasses RLS, never expose
SUPABASE_JWT_SECRET=your-jwt-secret

DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.xxxx.supabase.co:5432/postgres

MC_SEED=42                        # Monte Carlo reproducibility seed
```

**Rule:** The backend uses `SUPABASE_SERVICE_ROLE_KEY` for server-side operations.
The frontend uses only `SUPABASE_ANON_KEY`. Never send service role key to the client.

---

## Client Setup

```python
# backend/app/core/supabase.py

from supabase import create_client, Client
from app.core.config import settings
from functools import lru_cache


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Returns a singleton Supabase client using service role key.
    Uses lru_cache — safe because client is stateless.
    """
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
```

For async database access via SQLAlchemy (preferred for complex queries):

```python
# backend/app/core/db.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency for async DB sessions."""
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Row Level Security

RLS must be enabled on all tables that contain user data.
The backend service role bypasses RLS — use it only for admin/background tasks.
For user-scoped operations, use the anon client with `set_auth`:

```python
# When acting on behalf of a specific authenticated user:
client = get_supabase_client()
client.auth.set_session(access_token=user_jwt, refresh_token="")

# For background jobs (price updates, risk recalculation) — service role is fine:
client = get_supabase_client()  # already uses service role
```

Standard RLS policy pattern for positions table:

```sql
-- migrations/sql/rls_positions.sql
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only see their own positions"
ON positions FOR ALL
USING (auth.uid() = user_id);
```

---

## JWT Auth in FastAPI

```python
# backend/app/core/security.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Validates Supabase JWT and returns the user payload.
    Supabase uses HS256 with the JWT secret from the project dashboard.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Usage in a router:
@router.get("/positions")
async def list_positions(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["sub"]
    ...
```

---

## Upsert Pattern (Price Updates)

```python
# backend/app/services/price_service.py

async def upsert_prices(prices: list[PriceCreate], db: AsyncSession) -> None:
    """
    Insert or update price records. Uses PostgreSQL upsert on (ticker, date).
    Called by the daily GitHub Actions cron and the Airflow DAG.
    """
    stmt = pg_insert(PriceModel).values([p.model_dump() for p in prices])
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "price_date"],
        set_={
            "close_price": stmt.excluded.close_price,
            "price_source": stmt.excluded.price_source,
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()
```

---

## Storage: File Uploads (Excel/CSV)

```python
# backend/app/api/v1/imports.py

from fastapi import UploadFile, File
import pandas as pd
import io

STORAGE_BUCKET = "position-imports"


@router.post("/positions/import")
async def import_positions(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept Excel or CSV, validate schema row-by-row, return per-row errors.
    Also persist original file to Supabase Storage for audit trail.
    """
    content = await file.read()

    # 1. Store raw file in Supabase Storage
    client = get_supabase_client()
    storage_path = f"{user['sub']}/{file.filename}"
    client.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": file.content_type},
    )

    # 2. Parse
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        df = pd.read_excel(io.BytesIO(content))

    # 3. Validate row by row — see IMPORT_SCHEMA in KB
    errors = []
    valid_rows = []
    for idx, row in df.iterrows():
        try:
            position = PositionImportRow.model_validate(row.to_dict())
            valid_rows.append(position)
        except ValidationError as e:
            errors.append({"row": idx + 2, "errors": e.errors()})

    # 4. Insert valid rows
    if valid_rows:
        await bulk_insert_positions(valid_rows, user["sub"], db)

    return {
        "imported": len(valid_rows),
        "errors": errors,
        "storage_path": storage_path,
    }
```

---

## Migrations with Alembic

Even with Supabase, use Alembic to track schema changes as code:

```bash
# Initialize (once)
alembic init migrations

# Create a migration
alembic revision --autogenerate -m "add positions table"

# Apply
alembic upgrade head
```

`alembic.ini` should point to `DATABASE_URL` from env.
Alembic migrations live in `backend/migrations/versions/`.
RLS policies and custom indexes go in separate `.sql` files in `migrations/sql/`
and are applied manually or via a post-migration hook.

---

## Testing Supabase Endpoints

Use a separate Supabase project for tests (free tier allows multiple projects),
or mock the Supabase client:

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_supabase():
    with patch("app.core.supabase.get_supabase_client") as mock:
        mock.return_value = AsyncMock()
        yield mock.return_value


@pytest.fixture
async def test_db():
    """Use SQLite in-memory for unit tests, or a test Supabase project for integration."""
    ...
```
