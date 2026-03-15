# ГОСТ 34 — Система формирования отчётной документации

## Обзор проекта

Автоматизированная система для формирования, заполнения и согласования отчётной документации по ГОСТ 34 в рамках государственных контрактов. Облегчает взаимодействие заказчика и подрядчика.

**Ключевые возможности:**
- Справочник функций как единый источник данных для всех документов
- Генерация ТЗ, ЧТЗ, ПМИ (.docx по ГОСТ 2.105) и НМЦК (.xlsx с формулами)
- Работа с шаблонами документов (базовые по ГОСТам + пользовательские)
- Многораундовое согласование с участием обеих сторон контракта
- Полный аудит всех действий для разрешения конфликтных ситуаций
- Ролевая модель с разграничением прав заказчик/подрядчик

## Архитектура

4 микросервиса + shared пакет. Подробности: [docs/architecture.md](docs/architecture.md)

| Сервис | Ответственность | БД | Порт |
|--------|----------------|-----|------|
| Auth Service | Аутентификация, авторизация, роли, ПДн, аудит | PostgreSQL | 8001 |
| Catalog Service | Шаблоны, функции, подсистемы, ставки, документы | MongoDB | 8002 |
| Generation Service | Рендер .docx/.xlsx, ГОСТ 2.105, MinIO | — (stateless) | 8003 |
| Workflow Service | Согласование, раунды, решения, статусы | PostgreSQL | 8004 |

Общие механизмы вынесены в **shared** Python-пакет: JWT middleware, AuditLogger, CacheService, EventEmitter, HttpClient, ErrorHandler, HealthCheck.

## Стек технологий

- **Backend:** Python 3.12+, FastAPI, Uvicorn, Pydantic v2
- **Auth/Workflow DB:** PostgreSQL 16, SQLAlchemy 2.0, Alembic
- **Catalog DB:** MongoDB 7 CE, Motor/Beanie
- **Хранилище файлов:** MinIO (S3-совместимое)
- **Документы:** python-docx (.docx/.dotx), openpyxl (.xlsx)
- **Безопасность:** PyJWT (RS256), cryptography (AES-256), argon2-cffi, pyotp (TOTP)
- **Инфраструктура:** Docker, Docker Compose, nginx
- **Frontend:** React 18, Vite, React Router
- **Тесты:** pytest, pytest-asyncio, httpx

## Спецификации сервисов

Перед реализацией каждого сервиса — обязательно прочитать соответствующую спецификацию:

- [docs/auth-service-spec.md](docs/auth-service-spec.md) — Auth Service
- [docs/catalog-service-spec.md](docs/catalog-service-spec.md) — Catalog Service
- [docs/generation-service-spec.md](docs/generation-service-spec.md) — Generation Service
- [docs/workflow-service-spec.md](docs/workflow-service-spec.md) — Workflow Service
- [docs/shared-spec.md](docs/shared-spec.md) — Shared пакет
- [docs/permissions-matrix.md](docs/permissions-matrix.md) — Матрица прав (38 permissions × 7 ролей)
- [docs/security-requirements.md](docs/security-requirements.md) — Требования безопасности

## Ключевые архитектурные решения

1. **RS256 JWT + JWKS.** Auth подписывает приватным ключом, остальные верифицируют через `/.well-known/jwks.json` (кеш 1 час). Компрометация другого сервиса не позволяет выпускать токены.

2. **Side вычисляется из контекста проекта.** Организация не имеет фиксированной стороны. `side` определяется через `project.customer_org_id / contractor_org_id` при выпуске JWT.

3. **Локальный аудит в каждом сервисе.** AuditLogger пишет в локальную БД (атомарно с бизнес-операцией). Auth агрегирует через internal API. В v2 — Kafka + Audit Service.

4. **Render-bundle.** Generation получает всё необходимое одним запросом к Catalog: шаблон + данные + функции + подсистемы + ставки. Атомарно, без частичных отказов.

5. **Генерация на основе .dotx шаблона.** Вместо программного создания стилей — python-docx открывает .dotx с готовыми стилями и наполняет содержимым. STYLE_MAP маппит семантические элементы на имена стилей.

6. **Многораундовое согласование.** request → rounds → decisions. Раунд завершается, когда оба РП (заказчика и подрядчика) приняли решение. Приоритет: reject > revision > approve.

## Соглашения по коду

- **Python:** PEP 8, type hints обязательны, async/await везде
- **API:** RESTful, единый формат ошибок `{ "error": { "code": "...", "message": "...", "details": {} } }`
- **Пагинация:** `{ "items": [...], "total": N, "page": 1, "per_page": 20 }`
- **Health:** GET /health → `{ "status": "ok", "db": "connected", "version": "1.0.0" }`
- **Логирование:** structlog, JSON-формат, correlation_id (X-Request-ID) в каждой записи
- **Тесты:** pytest, минимум 1 интеграционный + unit на edge cases для каждого сервиса
- **Docker:** каждый сервис — свой Dockerfile, healthcheck обязателен

## Порядок разработки

1. **shared** → 2. **Auth Service** → 3. **Catalog Service** → 4a. **Generation Service** / 4b. **Workflow Service** (параллельно) → 5. **Интеграция** → 6. **Frontend**

## Инфраструктура

- `docker-compose.yml` — все сервисы, БД, MinIO, nginx
- `nginx/nginx.conf` — маршрутизация, CORS, TLS, X-Request-ID, блокировка /internal/*
- Каждый сервис запускает `alembic upgrade head` (или MongoDB seed) при старте
