from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.api import jobs, internal

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
        from app.storage.minio_client import init_minio, get_minio_client
        init_minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            templates_bucket=settings.MINIO_TEMPLATES_BUCKET,
            secure=settings.MINIO_SECURE,
            presigned_expiry=settings.PRESIGNED_URL_EXPIRY,
        )
        logger.info("minio_initialized", endpoint=settings.MINIO_ENDPOINT)

        # Загружаем дефолтный .dotx шаблон ГОСТ 2.105 в MinIO (идемпотентно)
        import io
        from pathlib import Path
        dotx_path = Path(__file__).parent.parent / "assets" / "gost-2105-template.dotx"
        if dotx_path.exists():
            minio = get_minio_client()
            dotx_bytes = dotx_path.read_bytes()
            minio._client.put_object(
                minio.templates_bucket,
                "gost-2105-template.dotx",
                io.BytesIO(dotx_bytes),
                length=len(dotx_bytes),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.template",
            )
            logger.info("dotx_template_uploaded", key="gost-2105-template.dotx")
        else:
            logger.warning("dotx_template_not_found", path=str(dotx_path))
    except Exception as exc:
        logger.warning("minio_init_failed", error=str(exc))

    yield
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
app.add_exception_handler(Exception, global_error_handler)
app.add_exception_handler(RequestValidationError, global_error_handler)

# ── Роутеры ──────────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(internal.router)
app.include_router(health_router)
