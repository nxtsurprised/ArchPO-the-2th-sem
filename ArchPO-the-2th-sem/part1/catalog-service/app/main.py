from __future__ import annotations
from contextlib import asynccontextmanager
import structlog
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, close_db, check_db_connection
from app.services import kafka_consumer

logger = structlog.get_logger()


async def _seed_system_templates() -> None:
    """Insert base system templates if they don't exist (idempotent)."""
    import json
    from pathlib import Path
    from app.models.template import Template

    seeds_dir = Path(__file__).parent.parent / "seeds" / "templates"
    for json_file in sorted(seeds_dir.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        template_id = data.pop("_id")
        existing = await Template.get(template_id)
        if existing:
            continue
        tmpl = Template(id=template_id, **data)
        await tmpl.insert()
        logger.info("template_seeded", id=template_id, name=tmpl.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db(settings)
    kafka_consumer.start_consumer(settings.KAFKA_BOOTSTRAP_SERVERS)

    try:
        await _seed_system_templates()
        logger.info("templates_seeded")
    except Exception as exc:
        logger.warning("templates_seed_failed", error=str(exc))

    logger.info("catalog_service_started", version=settings.APP_VERSION)
    yield
    await kafka_consumer.stop_consumer()
    await close_db()
    logger.info("catalog_service_stopped")


app = FastAPI(
    title="Catalog Service",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Correlation ID middleware ──────────────────────────────────────────────────
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    return response


# ── HTTP error handler ─────────────────────────────────────────────────────────
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    error = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error})


# ── Global error handler ───────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": {}}},
    )


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    db_ok = await check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "disconnected",
        "version": get_settings().APP_VERSION,
    }


# ── Prometheus /metrics ────────────────────────────────────────────────────────
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)

# ── Routes ─────────────────────────────────────────────────────────────────────
from app.api import templates, functions, subsystems, rates, documents, internal

app.include_router(templates.router, prefix="/api/catalog")
app.include_router(functions.router, prefix="/api/catalog")
app.include_router(subsystems.router, prefix="/api/catalog")
app.include_router(rates.router, prefix="/api/catalog")
app.include_router(documents.router, prefix="/api/catalog")
app.include_router(internal.router)
