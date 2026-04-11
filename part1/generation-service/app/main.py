from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.api import jobs, internal
from app.services import archive_service

from shared.logging.setup import configure_logging
from shared.middleware.correlation_id import correlation_id_middleware
from shared.middleware.error_handler import global_error_handler
from shared.health.checker import health_router

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("generation_service_starting", version=settings.APP_VERSION)

    # Инициализируем MinIO (best-effort: сервис stateless, MinIO может быть недоступен)
    try:
        from app.storage.minio_client import init_minio
        init_minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            templates_bucket=settings.MINIO_TEMPLATES_BUCKET,
            archive_bucket=settings.MINIO_ARCHIVE_BUCKET,
            secure=settings.MINIO_SECURE,
            presigned_expiry=settings.PRESIGNED_URL_EXPIRY,
        )
        logger.info("minio_initialized", endpoint=settings.MINIO_ENDPOINT)
    except Exception as exc:
        logger.warning("minio_init_failed", error=str(exc))

    # Запускаем фоновый воркер холодного хранилища
    archive_service.start_archive_worker(
        catalog_url=settings.CATALOG_SERVICE_URL,
        internal_secret=settings.INTERNAL_API_SECRET,
        archive_after_days=settings.ARCHIVE_AFTER_DAYS,
        interval_hours=settings.ARCHIVE_INTERVAL_HOURS,
    )

    yield
    await archive_service.stop_archive_worker()
    logger.info("generation_service_stopping")


app = FastAPI(
    title="Generation Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.middleware("http")(correlation_id_middleware)
app.add_exception_handler(FastAPIHTTPException, global_error_handler)
app.add_exception_handler(RequestValidationError, global_error_handler)
app.add_exception_handler(Exception, global_error_handler)

# ── Prometheus /metrics ───────────────────────────────────────────────────────
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)

# ── Роутеры ──────────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(internal.router)
app.include_router(health_router)
