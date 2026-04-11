# Auth Service — Спецификация

## Обзор

Аутентификация, авторизация, управление пользователями, организациями, проектами, ролями. Хранение ПДн с шифрованием. Полный аудит. JWKS-эндпоинт для других сервисов.

**БД:** PostgreSQL 16  
**ORM:** SQLAlchemy 2.0 + Alembic  
**Порт:** 8001

## Модель данных (12 таблиц)

### users
```sql
id                  UUID PK DEFAULT gen_random_uuid()
organization_id     UUID FK → organizations NOT NULL
email               VARCHAR(255) UNIQUE NOT NULL  -- корпоративный
phone_encrypted     TEXT                          -- AES-256 (ENCRYPT_KEY_PHONE)
password_hash       TEXT NOT NULL                 -- Argon2id
full_name           VARCHAR(255) NOT NULL
position            VARCHAR(255)
is_active           BOOLEAN DEFAULT true
is_superadmin       BOOLEAN DEFAULT false
is_2fa_required     BOOLEAN DEFAULT false
failed_login_attempts INT DEFAULT 0
locked_until        TIMESTAMP
password_expires_at TIMESTAMP
created_at          TIMESTAMP DEFAULT now()
updated_at          TIMESTAMP DEFAULT now()
```

### organizations
```sql
id            UUID PK DEFAULT gen_random_uuid()
name          VARCHAR(255) NOT NULL
inn           VARCHAR(12) UNIQUE NOT NULL
ogrn          VARCHAR(15) UNIQUE
legal_address TEXT
is_active     BOOLEAN DEFAULT true
created_at    TIMESTAMP DEFAULT now()
```
Организация нейтральна — side определяется контекстом проекта.

### projects
```sql
id                UUID PK DEFAULT gen_random_uuid()
name              VARCHAR(255) NOT NULL
code              VARCHAR(50) UNIQUE NOT NULL
description       TEXT
customer_org_id   UUID FK → organizations NOT NULL
contractor_org_id UUID FK → organizations NOT NULL
status            VARCHAR(20) DEFAULT 'active'  -- active / archived
created_at        TIMESTAMP DEFAULT now()
CONSTRAINT different_sides CHECK (customer_org_id != contractor_org_id)
```

### roles
```sql
id            UUID PK
name          VARCHAR(50) NOT NULL   -- pm, admin, analyst
display_name  VARCHAR(100) NOT NULL  -- "Руководитель проекта"
```
Роли — справочник. Side не хранится в роли, определяется через project.

### permissions
```sql
id          UUID PK
code        VARCHAR(100) UNIQUE NOT NULL  -- "function.edit_cost"
description TEXT
resource    VARCHAR(50)                    -- "function"
action      VARCHAR(50)                    -- "edit_cost"
```

### role_permissions
```sql
role_id       UUID FK → roles
permission_id UUID FK → permissions
PRIMARY KEY (role_id, permission_id)
```

### user_project_roles
```sql
id          UUID PK DEFAULT gen_random_uuid()
user_id     UUID FK → users NOT NULL
project_id  UUID FK → projects NOT NULL
role_id     UUID FK → roles NOT NULL
assigned_at TIMESTAMP DEFAULT now()
assigned_by UUID FK → users
UNIQUE (user_id, project_id)  -- один пользователь = одна роль в проекте
```

### sessions
```sql
id                  UUID PK DEFAULT gen_random_uuid()
user_id             UUID FK → users NOT NULL
refresh_token_hash  VARCHAR(255) NOT NULL
ip_address          VARCHAR(45)
user_agent          TEXT
created_at          TIMESTAMP DEFAULT now()
expires_at          TIMESTAMP NOT NULL
is_revoked          BOOLEAN DEFAULT false
```

### totp_devices
```sql
id                UUID PK DEFAULT gen_random_uuid()
user_id           UUID FK → users NOT NULL
secret_encrypted  TEXT NOT NULL     -- AES-256 (ENCRYPT_KEY_TOTP)
backup_codes_hash TEXT              -- JSON array of bcrypt hashes
is_active         BOOLEAN DEFAULT false
created_at        TIMESTAMP DEFAULT now()
```

### password_history
```sql
id            UUID PK DEFAULT gen_random_uuid()
user_id       UUID FK → users NOT NULL
password_hash TEXT NOT NULL
created_at    TIMESTAMP DEFAULT now()
```
Хранить последние 10 записей (FIFO).

### consent_records
```sql
id         UUID PK DEFAULT gen_random_uuid()
user_id    UUID FK → users NOT NULL
purpose    VARCHAR(100) NOT NULL  -- 'auth', 'notifications'
granted_at TIMESTAMP DEFAULT now()
revoked_at TIMESTAMP
ip_address VARCHAR(45)
```

### audit_log
```sql
id              UUID PK DEFAULT gen_random_uuid()
timestamp       TIMESTAMP NOT NULL DEFAULT now()
user_id         UUID NOT NULL
user_side       VARCHAR(20)
user_role       VARCHAR(20)
ip_address      VARCHAR(45)
user_agent      TEXT
service         VARCHAR(20) DEFAULT 'auth'
action          VARCHAR(100) NOT NULL
resource_type   VARCHAR(50) NOT NULL
resource_id     VARCHAR(100) NOT NULL
project_id      UUID
correlation_id  VARCHAR(100)
result          VARCHAR(20) DEFAULT 'success'
changes         JSONB
details         JSONB

-- Append-only: приложение имеет только INSERT
INDEX idx_audit_project_time (project_id, timestamp DESC)
INDEX idx_audit_user_time (user_id, timestamp DESC)
INDEX idx_audit_resource (resource_id, timestamp DESC)
```

## API-эндпоинты

### Аутентификация (public)
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/login` | Вход: email + password + totp_code? → access_token + refresh_token (httpOnly cookie). 401 / 423 locked |
| POST | `/api/auth/refresh` | Ротация refresh-токена → новый access_token. 401 если revoked |
| POST | `/api/auth/logout` | Инвалидация сессии. 204 |
| POST | `/api/auth/password/reset-request` | Запрос сброса пароля. Всегда 200 (не раскрывать наличие аккаунта) |
| POST | `/api/auth/password/reset-confirm` | Установка пароля по токену. 200 / 400 / 410 expired |

### Профиль и 2FA (auth required)
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/auth/me` | Профиль: ФИО, email (маскирован), роли по проектам, статус 2FA |
| PUT | `/api/auth/me/profile` | Обновление ФИО, телефона |
| PUT | `/api/auth/me/password` | Смена пароля (нужен текущий). Проверка истории 10 паролей |
| POST | `/api/auth/me/2fa/setup` | Генерация TOTP-секрета + QR + backup codes |
| POST | `/api/auth/me/2fa/confirm` | Активация 2FA (верификация кода) |
| DELETE | `/api/auth/me/2fa` | Отключение 2FA (нужен пароль). 403 если обязателен для роли |
| GET | `/api/auth/me/personal-data` | Полные ПДн субъекта (ст. 14 152-ФЗ). Логируется |
| POST | `/api/auth/me/deactivate` | Запрос деактивации + обезличивание через 30 дней |

### Администрирование (admin role)
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/auth/users` | Список пользователей (?project_id, ?side). ФИО маскировано для не-админов |
| POST | `/api/auth/users` | Создание аккаунта. Только своя сторона (org.side check) |
| PATCH | `/api/auth/users/:id/roles` | Назначение/отзыв роли в проекте. admin + pm |
| POST | `/api/auth/users/:id/deactivate` | Деактивация аккаунта. Только своя сторона |
| POST | `/api/auth/users/:id/unlock` | Ручная разблокировка |
| POST | `/api/auth/users/:id/force-logout` | Завершение всех сессий |
| GET | `/api/auth/audit` | Журнал аудита (?user_id, ?action, ?from, ?to). admin + pm |

### Superadmin
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/auth/organizations` | Список организаций |
| POST | `/api/auth/organizations` | Создание организации |
| PUT | `/api/auth/organizations/:id` | Обновление реквизитов |
| GET | `/api/auth/projects` | Список проектов (?org_id) |
| POST | `/api/auth/projects` | Создание проекта (customer_org_id + contractor_org_id) |
| PUT | `/api/auth/projects/:id` | Обновление (name, description) |
| POST | `/api/auth/projects/:id/archive` | Архивация |
| GET | `/api/auth/audit/unified` | Агрегированный аудит всех сервисов (?project_id, ?user_id, ?service, ?action, ?from, ?to) |
| GET | `/api/auth/audit/resource/:id/timeline` | Хронология объекта |
| GET | `/api/auth/audit/user/:id/activity` | Действия пользователя |
| GET | `/api/auth/audit/export` | Выгрузка в .xlsx (те же фильтры) |

### Internal API
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/.well-known/jwks.json` | Публичный ключ RS256 (public, кешируется) |
| GET | `/internal/users/:id` | ФИО, должность, org_name, org_side (без ПДн) |
| POST | `/internal/users/batch` | Пакетный запрос: { user_ids: [] } → { users: { id: UserInfo } } |
| GET | `/internal/users/:id/permissions?project_id=` | Роль + список permissions в проекте |
| GET | `/internal/audit` | Локальные аудит-записи (?user_id, ?from, ?to, ?project_id) |

## Безопасность

### Парольная политика
- Минимум 12 символов, 3 из 4 категорий (upper, lower, digits, special)
- Запрет: логин, ФИО, название системы в пароле
- История: 10 последних паролей (запрет повторного использования)
- Срок: 90 дней, предупреждение за 14 дней
- Хеширование: Argon2id (time_cost=3, memory_cost=65536)

### Блокировка
- 5 неудачных попыток → блокировка 30 мин
- Прогрессивная задержка: 0, 1, 2, 4 сек
- Уведомление на email при блокировке
- Rate limiting: 20 req/min на /auth/login с одного IP

### JWT
- Algorithm: RS256 (асимметричная подпись)
- Access token TTL: 15 мин
- Refresh token TTL: 7 дней, ротация при каждом использовании
- Idle timeout: 30 мин без активности
- Max concurrent sessions: 3 (вытеснение старейшей)

### Шифрование полей
- Телефон: AES-256 (Fernet, ключ ENCRYPT_KEY_PHONE)
- TOTP-секрет: AES-256 (Fernet, ключ ENCRYPT_KEY_TOTP)
- Пароль: Argon2id (необратимо)
- Ключи в MVP: переменные окружения (в продакшене — HashiCorp Vault)

### Маскирование в API
- Обычный пользователь: email → `iva***@domain.ru`, phone → `+7916***4567`, full_name → `Иванов И.А.`
- Администратор: полные данные, факт доступа логируется
- Другие сервисы (internal): только ФИО + должность + org (без email, phone)

### Обезличивание при деактивации
```sql
UPDATE users SET
    full_name = 'Пользователь ' || LEFT(id::text, 8),
    email = id::text || '@deactivated.local',
    phone_encrypted = NULL,
    password_hash = 'DEACTIVATED',
    is_active = false
WHERE id = :user_id;
DELETE FROM totp_devices WHERE user_id = :user_id;
DELETE FROM consent_records WHERE user_id = :user_id;
DELETE FROM password_history WHERE user_id = :user_id;
```

## Seed Data

При первом запуске (alembic + seed script):
1. Роли: pm, admin, analyst
2. 38 permissions (см. permissions-matrix.md)
3. role_permissions: маппинг по матрице
4. Superadmin аккаунт: admin@system.local / changeme (is_superadmin=true)
5. Тестовые организации: «Минстрой России» (ИНН 7707074507), «ООО СофтДев» (ИНН 7712345678)
6. Тестовый проект: «ГИС ЖКХ» (customer=Минстрой, contractor=СофтДев)

## Переменные окружения

```env
DB_HOST=auth-postgres
DB_PORT=5432
DB_NAME=auth_db
DB_USER=auth_user
DB_PASSWORD=<secret>
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem
JWT_ACCESS_TTL_SECONDS=900
JWT_REFRESH_TTL_SECONDS=604800
JWT_ALGORITHM=RS256
ENCRYPT_KEY_PHONE=<fernet_key>
ENCRYPT_KEY_TOTP=<fernet_key>
PASSWORD_MIN_LENGTH=12
PASSWORD_HISTORY_SIZE=10
PASSWORD_EXPIRY_DAYS=90
ARGON2_TIME_COST=3
ARGON2_MEMORY_COST=65536
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_SECONDS=1800
LOGIN_RATE_LIMIT=20/minute
MAX_CONCURRENT_SESSIONS=3
IDLE_TIMEOUT_SECONDS=1800
INTERNAL_API_SECRET=<secret>
SMTP_HOST=<host>
SMTP_PORT=587
SMTP_USER=<user>
SMTP_PASSWORD=<secret>
SMTP_FROM=noreply@system.gov.ru
```

## Тесты

**Интеграционный (1 сквозной):** регистрация → логин → access_token → GET /me → refresh → logout → refresh = 401

**Unit (6+):**
- Пароль не проходит политику → 400
- 5 неудачных попыток → 423 locked
- JWT с истёкшим exp → 401
- admin подрядчика создаёт аккаунт заказчика → 403
- Запрос без TOTP при обязательном 2FA → 403
- Маскирование телефона в ответе для не-админа

## Структура кода

```
auth-service/
  app/
    main.py
    config.py
    models/           # SQLAlchemy модели
    schemas/          # Pydantic request/response
    services/         # Бизнес-логика
    api/              # FastAPI роуты
    middleware/        # Rate limiting
  alembic/
    versions/
      001_initial_schema.py
      002_sessions_audit.py
      003_totp_consent.py
  seeds/
    seed_roles.py
    seed_permissions.py
    seed_test_data.py
  tests/
  Dockerfile
  requirements.txt
```
