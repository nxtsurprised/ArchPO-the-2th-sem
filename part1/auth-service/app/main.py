from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

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
