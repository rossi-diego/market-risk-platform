from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1 import basis as basis_router
from app.api.v1 import cbot as cbot_router
from app.api.v1 import fx as fx_router
from app.api.v1 import imports as imports_router
from app.api.v1 import physical as physical_router
from app.api.v1 import reports as reports_router
from app.api.v1 import risk as risk_router
from app.api.v1 import scenarios as scenarios_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.sentry import init_sentry
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_log import RequestLoggingMiddleware

logger = structlog.get_logger(__name__)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    configure_logging(settings.LOG_LEVEL)
    sentry_on = init_sentry()
    logger.info(
        "app.startup",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        sentry=sentry_on,
    )
    yield
    logger.info("app.shutdown", version=settings.APP_VERSION)


app = FastAPI(
    title="market-risk-platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

_TRUSTED_HOSTS = ["localhost", "127.0.0.1", "testserver", "*.vercel.app", "*.onrender.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["authorization", "content-type", "x-request-id"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_TRUSTED_HOSTS)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

api_router.include_router(physical_router.router)
api_router.include_router(cbot_router.router)
api_router.include_router(basis_router.router)
api_router.include_router(fx_router.router)
api_router.include_router(imports_router.router)
api_router.include_router(risk_router.router)
api_router.include_router(reports_router.router)
api_router.include_router(scenarios_router.router)

app.include_router(api_router)
