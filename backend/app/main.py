from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}


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

app.include_router(api_router)
