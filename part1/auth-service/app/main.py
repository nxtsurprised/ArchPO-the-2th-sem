from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.database import check_db_connection
from app.api import auth, me, admin, superadmin, internal
from app.middleware.rate_limit import setup_rate_limiter

from shared.logging.setup import configure_logging
from shared.middleware.correlation_id import correlation_id_middleware
from shared.middleware.error_handler import global_error_handler
from shared.health.checker import health_router, set_db_checker

# Настраиваем structlog до создания логгера, чтобы первые же сообщения
# выходили в правильном JSON-формате
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Код до yield – startup (подключения, прогрев кешей).
    Код после yield – shutdown (закрытие соединений).
    """
    logger.info("auth_service_starting", version=get_settings().APP_VERSION)
    yield
    logger.info("auth_service_stopping")


app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# ── Middleware (порядок важен: выполняются в обратном порядке регистрации) ──────

# correlation_id должен быть первым – он создаёт ID, который используют все остальные слои
app.middleware("http")(correlation_id_middleware)

# Глобальный обработчик ошибок – перехватывает Exception и RequestValidationError,
# возвращает единый формат { "error": { ... } }
app.add_exception_handler(Exception, global_error_handler)
app.add_exception_handler(RequestValidationError, global_error_handler)

# Rate limiting через slowapi – 20 req/min на /api/auth/login с одного IP
setup_rate_limiter(app)

# ── Prometheus /metrics ───────────────────────────────────────────────────────
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)

# ── Роутеры ─────────────────────────────────────────────────────────────────────

app.include_router(auth.router)        # /api/auth/login, /refresh, /logout, /password/*
app.include_router(me.router)          # /api/auth/me, /me/profile, /me/password, /me/2fa/*
app.include_router(admin.router)       # /api/auth/users/*, /audit
app.include_router(superadmin.router)  # /api/auth/organizations, /projects, /audit/unified
app.include_router(internal.router)    # /.well-known/jwks.json, /internal/*

# Подключаем health-эндпоинт (/health) из shared-пакета
# и передаём ему функцию для проверки подключения к PostgreSQL
set_db_checker(check_db_connection)
app.include_router(health_router)


# ── Swagger UI: кнопка "Authorize" с Bearer-токеном ─────────────────────────

# Публичные маршруты, которым НЕ нужна авторизация в документации
_PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/password/reset-request",
    "/api/auth/password/reset-confirm",
    "/.well-known/jwks.json",
    "/health",
    "/openapi.json",
    "/docs",
}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    # Добавляем секцию components.securitySchemes — именно она включает кнопку Authorize
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Вставьте access_token, полученный из POST /api/auth/login",
        }
    }

    # Помечаем все защищённые операции иконкой замка
    for path, path_item in schema.get("paths", {}).items():
        if path in _PUBLIC_PATHS:
            continue
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.setdefault("security", [{"BearerAuth": []}])

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
