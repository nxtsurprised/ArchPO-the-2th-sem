# Redis и кэширование в системе ГОСТ 34

## Обзор

В системе используется Redis как распределённое хранилище для кэша и счётчиков rate limiting.

До внедрения Redis сервисы использовали `CacheService` с in-memory dict: кэш не переживал
перезапуск сервиса и не разделялся между репликами. При масштабировании (несколько инстансов
одного сервиса) каждый инстанс держал свой изолированный кэш. Redis устраняет обе проблемы.

---

## Инфраструктура

### Брокер

| Параметр | Значение |
|---|---|
| Образ | `redis:7.2-alpine` |
| Адрес внутри Docker-сети | `redis:6379` |
| Порт наружу | `6379` |
| Политика вытеснения | `allkeys-lru` (при нехватке памяти удаляются старые ключи) |
| Лимит памяти | `256 MB` |
| Персистентность | RDB-снэпшот раз в 60 секунд (при наличии ≥1 изменения) |

### Разбивка по DB

Каждый сервис работает с отдельной логической базой Redis чтобы ключи не пересекались:

| Сервис | Redis DB | `REDIS_URL` |
|---|---|---|
| Auth Service | `db/3` | `redis://redis:6379/3` |
| Catalog Service | `db/0` | `redis://redis:6379/0` |
| Generation Service | `db/1` | `redis://redis:6379/1` |
| Workflow Service | `db/2` | `redis://redis:6379/2` |

---

## CacheService

**Файл:** `shared/shared/services/cache.py`

```python
class CacheService:
    def __init__(self, redis_url: str | None = None):
        # Если redis_url передан — используем Redis
        # Иначе — in-memory dict (для тестов / dev без Redis)
        ...

    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def close(self) -> None: ...
```

### Graceful degradation

Если Redis недоступен при запросе — `CacheService` **не падает**:

- При подключении: `redis_failed = True`, все последующие обращения идут в in-memory.
- При `get` / `set` / `delete`: ошибка логируется как `warning`, выполняется in-memory операция.

Таким образом Redis — ускоряющий элемент, а не критическая зависимость для бизнес-логики.

### Сериализация

Значения хранятся как `pickle`-байты. Это позволяет кэшировать любые Python-объекты:
JWT-ключи (`signing_key`), Pydantic-модели, словари. TTL задаётся через Redis `SETEX`.

---

## Где используется кэш

### JWKS (публичный ключ RS256)

**Сервис:** generation-service  
**Ключ:** `jwks:public_key`  
**TTL:** 3600 секунд (1 час)

Generation-service проверяет JWT-токены через JWKS-эндпоинт Auth Service. Без кэша
каждый запрос к generation-service делал бы HTTP-вызов в auth-service за публичным ключом.
С кэшем — один запрос в час на инстанс.

```
Входящий запрос с JWT
    │
    ▼
JWTAuth._get_public_key()
    │
    ├─ cache.get("jwks:public_key") → HIT → вернуть ключ (типичный путь)
    │
    └─ cache.get("jwks:public_key") → MISS
           │
           ▼
       HTTP GET auth-service/.well-known/jwks.json
           │
           ▼
       cache.set("jwks:public_key", key, ttl=3600)
           │
           ▼
       вернуть ключ
```

---

## Rate Limiting через Redis

**Сервис:** auth-service  
**Библиотека:** `slowapi` (обёртка над `limits`)  
**Файл:** `auth-service/app/middleware/rate_limit.py`

slowapi хранит счётчики запросов в Redis, что обеспечивает корректную работу
при нескольких репликах сервиса: все инстансы видят общий счётчик.

### Применённые лимиты

| Эндпоинт | Лимит (slowapi) | Лимит (nginx) |
|---|---|---|
| `POST /api/auth/login` | 20 req/min с IP | 20 req/min, burst 5 |
| `POST /api/auth/password/reset-request` | 5 req/min с IP | 20 req/min, burst 3 |

Двухуровневая защита: nginx блокирует на уровне TCP-соединения (до Python),
slowapi — на уровне приложения (учитывает логику сервиса).

---

## Конфигурация

`REDIS_URL` передаётся через переменную окружения.  
Если переменная не задана — `CacheService` работает в режиме in-memory (удобно для тестов).

```bash
# Пример .env
REDIS_URL=redis://redis:6379/0
```

---

## Связанные компоненты

- **Холодное хранилище** — архивный воркер в generation-service копирует файлы из MinIO `documents` → `documents-archive`. Redis здесь не участвует, но CacheService используется для JWKS в том же сервисе. Подробнее: [generation-service-spec.md](generation-service-spec.md).
- **Observability** — метрики Redis доступны через Prometheus scrape на `redis:6379`. Подробнее: [observability.md](observability.md).

---

## Расширение в будущем (v2)

| Что добавить | Зачем |
|---|---|
| JWT blacklist в Redis | Немедленный отзыв access-токенов при logout / force-logout (сейчас только refresh-сессия в PostgreSQL) |
| Кэш JWKS в catalog и workflow | Сейчас они используют `PyJWKClient` с встроенным 5-минутным кэшем; Redis даст общий кэш между репликами |
| Redis Sentinel / Cluster | Высокая доступность при отказе одного узла |
| Distributed lock (RedLock) | Исключить гонки при параллельном создании одного документа несколькими пользователями |
| Pub/Sub через Redis | Лёгкая альтернатива Kafka для внутренних уведомлений (например, инвалидация кэша между сервисами) |
