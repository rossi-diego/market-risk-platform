import os

import pytest

_ENV_DEFAULTS = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test",
    "SUPABASE_SERVICE_ROLE_KEY": "service-test",
    "SUPABASE_JWT_SECRET": "jwt-test",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
}

for key, value in _ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run @pytest.mark.integration tests (hit real Supabase).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require live infra (skipped unless --run-integration)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="requires --run-integration flag")
    for item in items:
        # Only skip tests that explicitly opted in via @pytest.mark.integration.
        # Checking `"integration" in item.keywords` would also match items under
        # the tests/integration/ folder whose names happen to contain that word.
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip_integration)
