"""Sentry initialization — lazy, env-gated.

`init_sentry()` is a no-op if `SENTRY_DSN` is not set, so dev runs stay quiet
while prod picks up the DSN from the environment. Traces sample rate is also
env-configurable; PII is disabled by default.
"""

from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings


def init_sentry() -> bool:
    """Initialize Sentry if `SENTRY_DSN` is set. Return True when activated."""
    if not settings.SENTRY_DSN:
        return False
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"market-risk-platform@{settings.APP_VERSION}",
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            AsyncPGIntegration(),
        ],
    )
    return True
