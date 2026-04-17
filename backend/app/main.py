import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.api.v1 import basis as basis_router
from app.api.v1 import cbot as cbot_router
from app.api.v1 import fx as fx_router
from app.api.v1 import imports as imports_router
from app.api.v1 import physical as physical_router
from app.api.v1 import risk as risk_router
from app.core.config import settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit a structured log line per request with request_id, user_id, timing."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        user_id = request.headers.get("x-user-id") or "anonymous"
        response.headers["x-request-id"] = request_id
        logger.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    configure_logging(settings.LOG_LEVEL)
    logger.info("app.startup", version=settings.APP_VERSION)
    yield
    logger.info("app.shutdown", version=settings.APP_VERSION)


app = FastAPI(
    title="market-risk-platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "testserver", "*.vercel.app"],
)
app.add_middleware(RequestLoggingMiddleware)

api_router.include_router(physical_router.router)
api_router.include_router(cbot_router.router)
api_router.include_router(basis_router.router)
api_router.include_router(fx_router.router)
api_router.include_router(imports_router.router)
api_router.include_router(risk_router.router)

app.include_router(api_router)
