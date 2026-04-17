import os

_ENV_DEFAULTS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test",
    "SUPABASE_SERVICE_ROLE_KEY": "service-test",
    "SUPABASE_JWT_SECRET": "jwt-test",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
}

for key, value in _ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
