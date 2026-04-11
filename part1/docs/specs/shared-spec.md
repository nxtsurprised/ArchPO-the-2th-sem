# Shared Package — Спецификация

## Обзор

Python-пакет с общими механизмами для всех микросервисов. Устанавливается через `pip install -e ../shared`. Содержит middleware, утилиты, Pydantic-схемы и сервисы-заглушки для v2.

## Структура

```
shared/
  schemas/
    user.py
    auth.py
    workflow.py
    audit.py
    pagination.py
    errors.py
  middleware/
    jwt_auth.py
    correlation_id.py
    error_handler.py
  services/
    http_client.py
    cache.py
    events.py
    audit.py
    audit_diff.py
  health/
    checker.py
  logging/
    setup.py
  setup.py           # pip package config
```

## Schemas

### user.py
```python
class UserInfo(BaseModel):
    """Ответ Auth /internal/users/:id"""
    id: UUID
    full_name: str
    position: str | None
    org_name: str
    org_side: Literal["customer", "contractor"]

class ProjectRole(BaseModel):
    project_id: UUID
    role: Literal["pm", "admin", "analyst"]
    side: Literal["customer", "contractor"]

class TokenPayload(BaseModel):
    """JWT payload после декодирования"""
    sub: UUID
    org_id: UUID
    roles: list[ProjectRole]
    exp: int
    iat: int
    is_superadmin: bool = False
```

### audit.py
```python
class AuditEntry(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID
    user_side: str | None
    user_role: str | None
    ip_address: str
    user_agent: str | None
    service: str
    action: str
    resource_type: str
    resource_id: str
    project_id: UUID | None
    correlation_id: str | None
    result: Literal["success", "failure", "denied"]
    changes: dict | None       # { field: { old, new } }
    details: dict | None
```

### pagination.py
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
```

### errors.py
```python
class ErrorDetail(BaseModel):
    code: str          # "DOCUMENT_LOCKED", "INVALID_PASSWORD"
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

## Middleware

### jwt_auth.py
```python
class JWTAuth:
    """
    Верификация JWT через JWKS.
    - Запрашивает /.well-known/jwks.json из Auth Service
    - Кеширует публичный ключ на 1 час (через CacheService)
    - Верифицирует подпись RS256
    - Парсит payload в TokenPayload
    - Добавляет request.state.user = TokenPayload
    """
    def __init__(self, auth_service_url: str, cache: CacheService): ...
    async def __call__(self, request: Request) -> TokenPayload: ...
```

### correlation_id.py
```python
async def correlation_id_middleware(request: Request, call_next):
    """
    X-Request-ID: если есть в запросе — использовать, иначе — сгенерировать UUID.
    Добавить в request.state.correlation_id и в response header.
    Все логи включают этот ID.
    """
```

### error_handler.py
```python
async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Единый формат: { "error": { "code": "...", "message": "...", "details": {} } }
    HTTPException → соответствующий статус
    ValidationError → 422
    Остальное → 500
    """
```

## Services

### http_client.py
```python
class InternalHttpClient:
    """
    Обёртка httpx.AsyncClient с:
    - connect_timeout=2s, read_timeout=5s
    - 2 retry с экспоненциальной задержкой (0.5s, 1s)
    - Автоматический проброс X-Request-ID и X-Internal-Secret
    - Логирование запросов/ответов через structlog
    """
```

### cache.py
```python
class CacheService:
    """
    Кеш с поддержкой TTL.

    Два режима:
    - Redis (production): CacheService(redis_url="redis://redis:6379/0")
    - In-memory fallback: CacheService() — если redis_url не задан или Redis недоступен

    При недоступности Redis автоматически переключается на in-memory без исключений.
    Значения сериализуются через pickle — поддерживает любые Python-объекты.

    async get(key: str) -> Any | None
    async set(key: str, value: Any, ttl_seconds: int = 3600) -> None
    async delete(key: str) -> None
    async exists(key: str) -> bool
    async close() -> None   # вызывать при shutdown
    """
```

Подробнее: [redis-cache.md](redis-cache.md)

### events.py
```python
# Конфигурация (один раз при старте):
events.configure(bootstrap_servers="kafka:9092", service_name="workflow")

class EventEmitter:
    """
    Kafka producer wrapper (aiokafka).
    Ключ сообщения = document_id → порядок событий для одного документа гарантирован.
    Graceful degradation: при недоступности Kafka логирует warning, запрос не прерывает.

    async emit(
        event_type: str,
        payload: dict,
        topic: str = "gost34.workflow.events",
        key: str | None = None,
    ) -> None
    """

# Utility
async def stop_producer() -> None   # вызывать при shutdown
```

Подробнее: [kafka-eda.md](kafka-eda.md)

### audit.py
```python
class AuditLogger:
    """
    Единый логгер для всех сервисов.
    Пишет в локальную БД (атомарно с бизнес-операцией).
    
    async log(
        action: str,
        user: TokenPayload,
        resource_type: str,
        resource_id: str,
        result: str = "success",
        changes: dict | None = None,
        details: dict | None = None,
        request: Request = None,
    ) -> None
    """
```

### audit_diff.py
```python
def compute_changes(old: dict, new: dict) -> dict | None:
    """
    Сравнивает два dict, возвращает изменённые поля:
    { "labor_hours": { "old": 120, "new": 80 } }
    Возвращает None если нет изменений.
    """
```

## Health

### checker.py
```python
health_router = APIRouter()

@health_router.get("/health")
async def health():
    """
    { "status": "ok", "db": "connected", "version": "1.0.0" }
    Проверяет подключение к БД.
    """
```

## Logging

### setup.py
```python
def configure_logging():
    """
    structlog config:
    - JSON формат
    - correlation_id в каждой записи
    - timestamp ISO 8601
    - level, logger, event
    """
```

## Использование в сервисах

```python
# main.py любого сервиса
from shared.middleware import correlation_id, error_handler
from shared.middleware.jwt_auth import JWTAuth
from shared.health import checker
from shared.logging import setup
from shared.services.cache import CacheService
from shared.services.events import EventEmitter
from shared.services.audit import AuditLogger

app = FastAPI()
setup.configure_logging()
app.middleware("http")(correlation_id.correlation_id_middleware)
app.exception_handler(Exception)(error_handler.global_error_handler)
app.include_router(checker.health_router)

cache = CacheService()
jwt_auth = JWTAuth(auth_service_url=config.AUTH_URL, cache=cache)
event_emitter = EventEmitter()
```
