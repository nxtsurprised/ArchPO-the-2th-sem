# Анализ реализованных микросервисов

## Содержание
1. [Перечень использованного ПО](#1-перечень-использованного-по)
2. [Auth Service — реализованные и нереализованные функции](#2-auth-service)
3. [Catalog Service — реализованные и нереализованные функции](#3-catalog-service)
4. [Generation Service — реализованные и нереализованные функции](#4-generation-service)
5. [Workflow Service — статус](#5-workflow-service)
6. [Сводная таблица](#6-сводная-таблица)

---

## 1. Перечень использованного ПО

### 1.1 Общий стек (все сервисы)

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.12+ | Основной язык |
| FastAPI | 0.109.2 | Web-фреймворк, REST API |
| Uvicorn | 0.27.1 | ASGI-сервер |
| Pydantic | 2.6.1 | Валидация данных, схемы |
| pydantic-settings | 2.2.1 | Конфигурация через env-переменные |
| PyJWT | 2.8.0 | Работа с JWT-токенами |
| cryptography | 42.0.4 | AES-256 шифрование полей (Fernet) |
| structlog | 24.1.0 | Структурированное JSON-логирование |
| httpx | 0.26.0 | Асинхронный HTTP-клиент (межсервисные запросы) |
| pytest | 8.0.2 | Тестирование |
| pytest-asyncio | 0.23.5 | Асинхронные тесты |

### 1.2 Auth Service (порт 8001)

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| SQLAlchemy | 2.0.27 | ORM для PostgreSQL |
| Alembic | 1.13.1 | Миграции схемы БД |
| asyncpg | 0.29.0 | Асинхронный драйвер PostgreSQL |
| psycopg2-binary | 2.9.9 | Синхронный драйвер PostgreSQL (для Alembic) |
| aiosqlite | 0.20.0 | SQLite для тестовой среды |
| argon2-cffi | 23.1.0 | Хеширование паролей (Argon2id) |
| pyotp | 2.9.0 | Генерация и верификация TOTP (2FA) |
| python-multipart | 0.0.9 | Поддержка form-data |
| aiosmtplib | 3.0.1 | Асинхронная отправка email (установлена, не используется в MVP) |
| openpyxl | 3.1.2 | Экспорт аудита в .xlsx (установлена, не используется в MVP) |
| slowapi | 0.1.9 | Rate limiting |
| limits | 3.9.0 | Backend для slowapi |

**БД:** PostgreSQL 16-alpine

### 1.3 Catalog Service (порт 8002)

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| motor | 3.6.0 | Асинхронный драйвер MongoDB |
| pymongo | 4.9.2 | Синхронный драйвер MongoDB |
| beanie | 1.26.0 | ODM для MongoDB (поверх motor) |
| python-multipart | 0.0.9 | Поддержка form-data |
| mongomock-motor | 0.0.21 | Mock MongoDB для тестов |

**БД:** MongoDB 7.0

### 1.4 Generation Service (порт 8003)

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| python-docx | 1.1.2 | Генерация .docx документов (ТЗ, ЧТЗ, ПМИ) |
| openpyxl | 3.1.2 | Генерация .xlsx документов (НМЦК) |
| minio | 7.2.5 | S3-совместимое хранилище (MinIO SDK) |
| aiosqlite | 0.20.0 | SQLite для аудит-лога в тестах |

**БД:** нет (stateless, job-ы in-memory)

### 1.5 Инфраструктура

| Компонент | Версия | Назначение |
|-----------|--------|-----------|
| PostgreSQL | 16-alpine | БД Auth Service и Workflow Service |
| MongoDB | 7.0 | БД Catalog Service |
| MinIO | latest | S3-совместимое объектное хранилище (.docx/.xlsx файлы) |
| nginx | 1.25-alpine | API Gateway, маршрутизация, блокировка /internal/* |
| Docker | — | Контейнеризация |
| Docker Compose | 3.9 | Оркестрация сервисов |

---

## 2. Auth Service

### ✅ Реализовано

#### Аутентификация (public endpoints)
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| POST | `/api/auth/login` | ✅ | Argon2id, TOTP, httpOnly cookie для refresh |
| POST | `/api/auth/refresh` | ✅ | Ротация refresh-токена |
| POST | `/api/auth/logout` | ✅ | Инвалидация сессии, удаление cookie |
| POST | `/api/auth/password/reset-request` | ✅ частично | Заглушка: всегда 200, письмо не отправляется |
| POST | `/api/auth/password/reset-confirm` | ⚠️ | Заглушка: всегда 400 NOT_IMPLEMENTED |

#### Профиль и 2FA (требуется JWT)
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/auth/me` | ✅ | Роли по проектам, флаг 2FA |
| PUT | `/api/auth/me/profile` | ✅ | AES-256 для телефона, аудит diff |
| PUT | `/api/auth/me/password` | ✅ | Политика, история 10 паролей |
| POST | `/api/auth/me/2fa/setup` | ✅ | TOTP секрет + QR URI + backup codes |
| POST | `/api/auth/me/2fa/confirm` | ✅ | Активация устройства |
| DELETE | `/api/auth/me/2fa` | ✅ | Проверка is_2fa_required |
| GET | `/api/auth/me/personal-data` | ✅ | Расшифровка телефона, аудит доступа |
| POST | `/api/auth/me/deactivate` | ✅ | Обезличивание (MVP: мгновенно) |

#### Администрирование (роль admin/pm)
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/auth/users` | ✅ | Маскирование ПДн для не-админов, пагинация |
| POST | `/api/auth/users` | ✅ | Проверка cross-org, политика паролей |
| PATCH | `/api/auth/users/:id/roles` | ✅ | Upsert роли в проекте |
| POST | `/api/auth/users/:id/deactivate` | ✅ | Проверка cross-org |
| POST | `/api/auth/users/:id/unlock` | ✅ | Сброс failed_login_attempts |
| POST | `/api/auth/users/:id/force-logout` | ✅ | Отзыв всех сессий |
| GET | `/api/auth/audit` | ✅ | Фильтры: user_id, action, from/to |

#### Superadmin
| Метод | Путь | Статус |
|-------|------|--------|
| GET | `/api/auth/organizations` | ✅ |
| POST | `/api/auth/organizations` | ✅ |
| PUT | `/api/auth/organizations/:id` | ✅ |
| GET | `/api/auth/projects` | ✅ |
| POST | `/api/auth/projects` | ✅ |
| PUT | `/api/auth/projects/:id` | ✅ |
| POST | `/api/auth/projects/:id/archive` | ✅ |
| GET | `/api/auth/audit/unified` | ✅ |
| GET | `/api/auth/audit/resource/:id/timeline` | ✅ |
| GET | `/api/auth/audit/user/:id/activity` | ✅ |

#### Internal API
| Метод | Путь | Статус |
|-------|------|--------|
| GET | `/.well-known/jwks.json` | ✅ |
| GET | `/internal/users/:id` | ✅ |
| POST | `/internal/users/batch` | ✅ |
| GET | `/internal/users/:id/permissions` | ✅ |
| GET | `/internal/audit` | ✅ |

#### Безопасность и инфраструктура
- ✅ RS256 JWT (асимметричная подпись)
- ✅ Access token TTL 15 мин, Refresh token TTL 7 дней с ротацией
- ✅ AES-256 (Fernet) шифрование телефона и TOTP-секрета
- ✅ Argon2id для хеширования паролей (time_cost=3, memory_cost=65536)
- ✅ Блокировка после 5 неудачных попыток (30 мин)
- ✅ Политика паролей (длина, категории, история, срок действия)
- ✅ Маскирование ПДн в API (email, ФИО)
- ✅ Обезличивание при деактивации (152-ФЗ)
- ✅ Полный аудит (append-only log)
- ✅ Seed данные: роли, superadmin, тестовые организации/проект
- ✅ Alembic миграции (1 файл с начальной схемой)

### ❌ Не реализовано / Заглушки

| Функция | Статус | Примечание |
|---------|--------|-----------|
| `POST /api/auth/password/reset-confirm` | ⚠️ заглушка | Логика сброса по токену из email не реализована |
| `GET /api/auth/audit/export` | ❌ | Выгрузка аудита в .xlsx отсутствует (openpyxl установлен) |
| Отправка email при блокировке | ❌ | aiosmtplib установлен, интеграция не реализована |
| Rate limiting на `/auth/login` | ❌ | slowapi установлен, middleware не подключён |
| Прогрессивная задержка при неудачных входах | ❌ | Только блокировка, без задержки 0/1/2/4 сек |
| Ограничение MAX_CONCURRENT_SESSIONS=3 | ❌ | Конфигурация есть, логика вытеснения не реализована |
| Idle timeout (30 мин) | ❌ | Конфигурация есть, проверка не реализована |
| Alembic: миграции 002, 003 | ❌ | В спецификации: `002_sessions_audit.py`, `003_totp_consent.py`; только `001_initial_schema.py` |

---

## 3. Catalog Service

### ✅ Реализовано

#### Шаблоны
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/catalog/templates` | ✅ | Фильтры: project_id, type |
| GET | `/api/catalog/templates/:id` | ✅ | |
| POST | `/api/catalog/templates` | ✅ | Проверка ролей, аудит |
| PUT | `/api/catalog/templates/:id` | ✅ | Защита системных шаблонов |
| DELETE | `/api/catalog/templates/:id` | ✅ | 409 для is_system=true |

#### Справочник функций
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/catalog/functions` | ✅ | Фильтры: project_id, category, subsystem_id, q |
| GET | `/api/catalog/functions/:id` | ✅ | |
| POST | `/api/catalog/functions` | ✅ | |
| PUT | `/api/catalog/functions/:id` | ✅ | Cost/priority — только pm |
| DELETE | `/api/catalog/functions/:id` | ✅ | Soft delete (status=deleted) |

#### Подсистемы
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/catalog/subsystems` | ✅ | Сортировка по order |
| POST | `/api/catalog/subsystems` | ✅ | |
| PUT | `/api/catalog/subsystems/:id` | ✅ | |
| PUT | `/api/catalog/subsystems/reorder` | ✅ | |
| DELETE | `/api/catalog/subsystems/:id` | ✅ | 409 при наличии активных функций |

#### Ставки
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/catalog/rates` | ✅ | |
| PUT | `/api/catalog/rates/:project_id` | ✅ | Upsert |

#### Документы
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| GET | `/api/catalog/documents` | ✅ | Фильтры: project_id, type |
| GET | `/api/catalog/documents/:id` | ✅ | |
| POST | `/api/catalog/documents` | ✅ | |
| PUT | `/api/catalog/documents/:id` | ✅ | 409 при статусе pending/approved |
| DELETE | `/api/catalog/documents/:id` | ✅ | |
| POST | `/api/catalog/documents/:id/validate` | ✅ | Валидация полноты документа |

#### Internal API
| Метод | Путь | Статус |
|-------|------|--------|
| GET | `/internal/documents/:id/render-bundle` | ✅ |
| GET | `/internal/audit` | ✅ |

### ❌ Не реализовано

| Функция | Статус | Примечание |
|---------|--------|-----------|
| `DELETE /functions/:id` — 409 при привязке к согласованному документу | ❌ | Soft delete выполняется без проверки статуса документов в Workflow |
| `PATCH /internal/functions/batch-update-refs` | ❌ | Endpoint для обратной связи от Generation (обновление doc_refs.tz_section) отсутствует |

---

## 4. Generation Service

### ✅ Реализовано

#### API
| Метод | Путь | Статус | Примечание |
|-------|------|--------|-----------|
| POST | `/api/generation/jobs` | ✅ | Idempotency: возвращает существующий job |
| GET | `/api/generation/jobs/:job_id` | ✅ | Статусы: pending/processing/completed/failed |
| GET | `/api/generation/jobs/:job_id/download` | ✅ | SHA-256 проверка, redirect на presigned URL |
| GET | `/api/generation/documents/:document_id/files` | ✅ | История генераций |
| GET | `/internal/audit` | ✅ | In-memory аудит |

#### Пайплайн генерации
| Этап | Компонент | Статус | Примечание |
|------|-----------|--------|-----------|
| 1. Валидация | `validator.py` / `BundleValidator` | ✅ | Проверка обязательных полей |
| 2. Диспетчер секций | `section_renderer.py` / `SectionRenderer` | ✅ | Маршрутизация по source-типу |
| 3а. Ручные секции | `renderers/manual_renderer.py` | ✅ | Заполненные пользователем поля |
| 3б. Функции | `renderers/function_renderer.py` | ✅ | Группировка по подсистемам, H3/H4/paragraphs |
| 3в. Статический контент | `renderers/static_renderer.py` | ✅ | |
| 4. Форматирование | `formatters/gost_formatter.py` | ✅ | ГОСТ 2.105-2019, STYLE_MAP, fallback-стили |
| 5а. Сборка .docx | `formatters/docx_builder.py` | ✅ | python-docx, поддержка .dotx шаблона |
| 5б. Сборка .xlsx | `formatters/xlsx_builder.py` | ✅ | openpyxl, 3 листа, формулы НМЦК |
| 6. Сохранение | `storage/minio_client.py` | ✅ | MinIO, SHA-256, presigned URL |
| 7. Аудит | `services/audit_store.py` | ✅ | Запись событий generation.start/complete/failed/download |

### ❌ Не реализовано

| Функция | Статус | Примечание |
|---------|--------|-----------|
| Этап 6: обратная связь в Catalog | ❌ | `PATCH /internal/functions/batch-update-refs` после генерации не вызывается |
| 3 retry с экспоненциальной задержкой при отказе MinIO | ⚠️ | Спецификация требует retry, реализация не подтверждена |

---

## 5. Workflow Service

### ❌ Не реализован

Workflow Service объявлен в `docker-compose.yml` (порт 8004, БД workflow-postgres), однако **директория `workflow-service/` в репозитории отсутствует**. Сервис ни в каком виде не реализован.

Согласно спецификации ([docs/workflow-service-spec.md](docs/workflow-service-spec.md)), Workflow Service должен обеспечивать:
- Создание и управление запросами на согласование документов
- Многораундовое согласование (request → rounds → decisions)
- Статусы документов и переходы между ними
- Уведомления участников процесса

---

## 6. Сводная таблица

| Микросервис | Реализовано API | Не реализовано | Инфраструктура |
|-------------|-----------------|----------------|----------------|
| **Auth Service** | 28 / 30 эндпоинтов | Экспорт аудита в xlsx, реальный reset-confirm, rate limiting, email-уведомления | PostgreSQL ✅ |
| **Catalog Service** | 17 / 17 эндпоинтов | batch-update-refs, проверка при soft-delete функции | MongoDB ✅ |
| **Generation Service** | 5 / 5 эндпоинтов, полный pipeline | Обратная связь с Catalog | MinIO ✅ |
| **Workflow Service** | 0 / N эндпоинтов | Весь сервис | PostgreSQL (не заполнен) |

### Общие замечания

1. **Shared-пакет реализован** — JWT middleware, AuditLogger, CacheService (базовый), HttpClient, ErrorHandler, HealthCheck, Correlation ID middleware.
2. **Workflow Service отсутствует** — это блокирует E2E сценарий согласования и препятствует проверке 409 при попытке удалить функцию, привязанную к согласованному документу.
3. **Три Alembic-миграции из спецификации не разделены** — весь DDL находится в одном файле `001_initial_schema.py` вместо трёх (`001`, `002_sessions_audit`, `003_totp_consent`).
4. **Rate limiting установлен** (slowapi), но не подключён к роутеру `/auth/login`.
5. **Email-уведомления** (aiosmtplib) установлены, но SMTP-интеграция не реализована.
