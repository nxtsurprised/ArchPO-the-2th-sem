# Тест-кейсы Auth Service

**Swagger UI:** http://localhost:8001/docs
**Среда:** локальная, Docker Compose

Сид создаёт готовые данные:
- **Суперадмин:** `admin@system.local` / `changeme`
- **Организации:** Минстрой (`22222222-0000-0000-0000-000000000001`), ООО СофтДев (`22222222-0000-0000-0000-000000000002`)
- **Проект:** ГИС ЖКХ, код `GIS-ZKH` (`44444444-0000-0000-0000-000000000001`)

---

## Блок 1 — Аутентификация (без токена)

### TC-01: Успешный вход

**Эндпоинт:** `POST /api/auth/login`

**Тело запроса:**
```json
{ "email": "admin@system.local", "password": "changeme" }
```

**Ожидаемый результат:** `200 OK`
```json
{ "access_token": "<jwt>", "expires_in": 900 }
```

**Действие после:** скопировать `access_token`, нажать **Authorize** в Swagger, вставить токен.

---

### TC-02: Неверный пароль

**Эндпоинт:** `POST /api/auth/login`

**Тело запроса:**
```json
{ "email": "admin@system.local", "password": "wrongpassword" }
```

**Ожидаемый результат:** `401 Unauthorized`
```json
{ "error": { "code": "INVALID_CREDENTIALS", "message": "..." } }
```

---

### TC-03: Несуществующий пользователь

**Эндпоинт:** `POST /api/auth/login`

**Тело запроса:**
```json
{ "email": "nobody@example.com", "password": "anypassword" }
```

**Ожидаемый результат:** `401 Unauthorized`, тот же `INVALID_CREDENTIALS`
**Важно:** ответ не должен сообщать, что email не найден — защита от перебора аккаунтов.

---

### TC-04: Блокировка после 5 неудачных попыток

**Эндпоинт:** `POST /api/auth/login` — выполнить **6 раз подряд** с неверным паролем

**Тело запроса:**
```json
{ "email": "admin@system.local", "password": "wrong" }
```

| Попытка | Ожидаемый статус |
|---------|-----------------|
| 1–5     | `401`           |
| 6       | `423` (аккаунт заблокирован на 30 минут) |

---

### TC-05: Сброс пароля — антиперебор

**Эндпоинт:** `POST /api/auth/password/reset-request`

**Тело запроса:**
```json
{ "email": "doesnotexist@example.com" }
```

**Ожидаемый результат:** `200 OK`
```json
{ "message": "Если аккаунт существует, инструкции отправлены на email" }
```

**Важно:** ответ одинаковый независимо от того, существует email или нет.

---

### TC-06: Подтверждение сброса пароля (MVP-заглушка)

**Эндпоинт:** `POST /api/auth/password/reset-confirm`

**Тело запроса:**
```json
{ "token": "any-token", "new_password": "NewPass123!" }
```

**Ожидаемый результат:** `400 Bad Request`
```json
{ "error": { "code": "NOT_IMPLEMENTED", "message": "..." } }
```

---

## Блок 2 — Сессии (refresh-токен)

> Refresh-токен приходит в httpOnly cookie, Swagger UI его не подхватывает.
> Для TC-07–09 использовать **curl** или **Postman** с сохранением cookies.

### TC-07: Обновление токена

```bash
# Шаг 1 — логин, сохранить cookie
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@system.local","password":"changeme"}'

# Шаг 2 — обновить токен
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8001/api/auth/refresh
```

**Ожидаемый результат:** `200 OK`, новый `access_token` в теле, новый `refresh_token` в cookie.

---

### TC-08: Повторное использование старого refresh-токена (детекция угона)

```bash
# Шаг 1 — логин
curl -c cookies1.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@system.local","password":"changeme"}'

# Шаг 2 — первый refresh (токен ротируется, старый инвалидируется)
curl -b cookies1.txt -c cookies2.txt -X POST http://localhost:8001/api/auth/refresh

# Шаг 3 — повторный refresh со старым токеном
curl -b cookies1.txt -X POST http://localhost:8001/api/auth/refresh
```

| Шаг | Ожидаемый результат |
|-----|---------------------|
| 2   | `200 OK`            |
| 3   | `401 Unauthorized`  |

---

### TC-09: Выход из системы

```bash
curl -b cookies.txt -X POST http://localhost:8001/api/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

**Ожидаемый результат:** `204 No Content`, cookie `refresh_token` сброшен.

---

## Блок 3 — Профиль (требует Authorize в Swagger)

### TC-10: Получить профиль текущего пользователя

**Эндпоинт:** `GET /api/auth/me`

**Ожидаемый результат:** `200 OK`
```json
{
  "id": "33333333-0000-0000-0000-000000000001",
  "email": "admin@system.local",
  "full_name": "Системный Администратор",
  "is_superadmin": true,
  "is_2fa_enabled": false,
  "roles": []
}
```

---

### TC-11: Обновить профиль

**Эндпоинт:** `PUT /api/auth/me/profile`

**Тело запроса:**
```json
{ "full_name": "Тест Тестов", "position": "Главный тестировщик" }
```

**Ожидаемый результат:** `200 OK`, сообщение об успехе.
**Проверка:** повторить TC-10 — `full_name` и `position` должны обновиться.

---

### TC-12: Смена пароля — валидный пароль

**Эндпоинт:** `PUT /api/auth/me/password`

**Тело запроса:**
```json
{ "current_password": "changeme", "new_password": "NewPass123!" }
```

**Ожидаемый результат:** `200 OK`
**После теста:** вернуть пароль обратно (`NewPass123!` → `changeme`).

---

### TC-13: Смена пароля — слабый пароль

**Эндпоинт:** `PUT /api/auth/me/password`

**Тело запроса:**
```json
{ "current_password": "changeme", "new_password": "weak" }
```

**Ожидаемый результат:** `400 Bad Request`, описание нарушений политики пароля.

---

### TC-14: Запрос без токена

**Эндпоинт:** `GET /api/auth/me` — без Authorize (или после нажатия Logout в Swagger)

**Ожидаемый результат:** `401 Unauthorized`
```json
{ "error": { "code": "UNAUTHORIZED", "message": "Требуется авторизация" } }
```

---

## Блок 4 — Управление пользователями (суперадмин)

### TC-15: Список пользователей

**Эндпоинт:** `GET /api/auth/users`

**Ожидаемый результат:** `200 OK`, пагинированный список
```json
{ "items": [...], "total": 1, "page": 1, "per_page": 20 }
```

---

### TC-16: Создать пользователя

**Эндпоинт:** `POST /api/auth/users`

**Тело запроса:**
```json
{
  "email": "testuser@example.com",
  "password": "TestUser123!",
  "full_name": "Тест Пользователь",
  "org_id": "22222222-0000-0000-0000-000000000001"
}
```

**Ожидаемый результат:** `201 Created`, объект пользователя с `id`.
**Сохранить:** `id` нового пользователя для TC-18–19.

---

### TC-17: Создать пользователя с занятым email

**Эндпоинт:** `POST /api/auth/users` — тот же email, что в TC-16

**Тело запроса:**
```json
{
  "email": "testuser@example.com",
  "password": "AnotherPass123!",
  "full_name": "Другой Пользователь",
  "org_id": "22222222-0000-0000-0000-000000000001"
}
```

**Ожидаемый результат:** `409 Conflict`

---

### TC-18: Назначить роль пользователю

**Эндпоинт:** `PATCH /api/auth/users/{id}/roles`
`{id}` — из TC-16

**Тело запроса:**
```json
{
  "project_id": "44444444-0000-0000-0000-000000000001",
  "role_name": "analyst"
}
```

**Ожидаемый результат:** `200 OK`

---

### TC-19: Роль отображается в JWT нового пользователя

**Эндпоинт:** `POST /api/auth/login`

**Тело запроса:**
```json
{ "email": "testuser@example.com", "password": "TestUser123!" }
```

**Проверка:** декодировать `access_token` на https://jwt.io
**Ожидаемый результат:** в payload поле `roles` содержит запись с `role: "analyst"` и `project_id: "44444444-0000-0000-0000-000000000001"`.

---

### TC-20: Деактивировать пользователя

**Эндпоинт:** `POST /api/auth/users/{id}/deactivate`
`{id}` — из TC-16

**Ожидаемый результат:** `200 OK`
**Проверка:** попытка логина под этим пользователем должна вернуть `401`.

---

## Блок 5 — Организации и проекты (суперадмин)

### TC-21: Список организаций

**Эндпоинт:** `GET /api/auth/organizations`

**Ожидаемый результат:** `200 OK`, минимум 2 записи (Минстрой и ООО СофтДев).

---

### TC-22: Создать организацию

**Эндпоинт:** `POST /api/auth/organizations`

**Тело запроса:**
```json
{ "name": "ООО Тест", "inn": "9900000001" }
```

**Ожидаемый результат:** `201 Created`

---

### TC-23: Создать организацию с дублирующимся ИНН

**Эндпоинт:** `POST /api/auth/organizations`

**Тело запроса:**
```json
{ "name": "Другое название", "inn": "9900000001" }
```

**Ожидаемый результат:** `409 Conflict`

---

### TC-24: Список проектов

**Эндпоинт:** `GET /api/auth/projects`

**Ожидаемый результат:** `200 OK`, содержит проект ГИС ЖКХ.

---

### TC-25: Создать проект где заказчик = подрядчик

**Эндпоинт:** `POST /api/auth/projects`

**Тело запроса:**
```json
{
  "name": "Некорректный проект",
  "code": "BAD-001",
  "customer_org_id": "22222222-0000-0000-0000-000000000001",
  "contractor_org_id": "22222222-0000-0000-0000-000000000001"
}
```

**Ожидаемый результат:** `400 Bad Request` (заказчик не может совпадать с подрядчиком).

---

### TC-26: Создать корректный проект

**Эндпоинт:** `POST /api/auth/projects`

**Тело запроса:**
```json
{
  "name": "Тестовый проект",
  "code": "TEST-001",
  "customer_org_id": "22222222-0000-0000-0000-000000000001",
  "contractor_org_id": "22222222-0000-0000-0000-000000000002"
}
```

**Ожидаемый результат:** `201 Created`

---

## Блок 6 — Internal API (без авторизации, только заголовок)

> Эндпоинты доступны только внутри Docker-сети.
> При тестировании снаружи использовать curl с заголовком `X-Internal-Secret`.
> Значение секрета: переменная `INTERNAL_API_SECRET` из docker-compose.yml (по умолчанию `internal_secret`).

### TC-27: Получить публичный ключ (JWKS)

**Эндпоинт:** `GET /.well-known/jwks.json`

**Ожидаемый результат:** `200 OK`
```json
{ "keys": [{ "kty": "RSA", "use": "sig", "alg": "RS256", "n": "...", "e": "AQAB" }] }
```

---

### TC-28: Внутренний профиль пользователя

```bash
curl http://localhost:8001/internal/users/33333333-0000-0000-0000-000000000001 \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`, объект без PII (нет email, phone):
```json
{ "id": "...", "full_name": "...", "position": "...", "org_name": "...", "org_side": null }
```

---

### TC-29: Права пользователя по проекту

```bash
curl "http://localhost:8001/internal/users/33333333-0000-0000-0000-000000000001/permissions?project_id=44444444-0000-0000-0000-000000000001" \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`
```json
{ "role": null, "permissions": [] }
```
*(Суперадмин не имеет проектной роли — права проверяются через флаг `is_superadmin`)*

---

### TC-30: Internal без секрета

```bash
curl http://localhost:8001/internal/users/33333333-0000-0000-0000-000000000001
```

**Ожидаемый результат:** `403 Forbidden`

---

## Блок 7 — Аудит

### TC-31: Просмотр аудит-лога

**Эндпоинт:** `GET /api/auth/audit`

**Ожидаемый результат:** `200 OK`, записи о входах из предыдущих тестов.
**Проверить наличие полей:** `timestamp`, `action`, `result`, `correlation_id`, `ip_address`.

---

### TC-32: Фильтрация аудита по действию

**Эндпоинт:** `GET /api/auth/audit?action=login.success`

**Ожидаемый результат:** `200 OK`, только записи с успешными входами.

---

## Сводная таблица

| №     | Эндпоинт                              | Что проверяет                          | Ожидаемый статус |
|-------|---------------------------------------|----------------------------------------|-----------------|
| TC-01 | POST /api/auth/login                  | Успешный вход                          | 200             |
| TC-02 | POST /api/auth/login                  | Неверный пароль                        | 401             |
| TC-03 | POST /api/auth/login                  | Несуществующий email, антиперебор      | 401             |
| TC-04 | POST /api/auth/login ×6               | Блокировка аккаунта                    | 423 (6-я)       |
| TC-05 | POST /password/reset-request          | Нет утечки email                       | 200             |
| TC-06 | POST /password/reset-confirm          | MVP-заглушка                           | 400             |
| TC-07 | POST /api/auth/refresh                | Ротация токенов                        | 200             |
| TC-08 | POST /api/auth/refresh (старый токен) | Детекция угона сессии                  | 401             |
| TC-09 | POST /api/auth/logout                 | Выход, сброс cookie                    | 204             |
| TC-10 | GET /api/auth/me                      | Профиль пользователя                   | 200             |
| TC-11 | PUT /api/auth/me/profile              | Обновление профиля                     | 200             |
| TC-12 | PUT /api/auth/me/password             | Смена пароля (валидный)                | 200             |
| TC-13 | PUT /api/auth/me/password             | Смена пароля (слабый)                  | 400             |
| TC-14 | GET /api/auth/me (без токена)         | Защита эндпоинта                       | 401             |
| TC-15 | GET /api/auth/users                   | Список пользователей с пагинацией      | 200             |
| TC-16 | POST /api/auth/users                  | Создание пользователя                  | 201             |
| TC-17 | POST /api/auth/users (дубль email)    | Уникальность email                     | 409             |
| TC-18 | PATCH /api/auth/users/{id}/roles      | Назначение роли                        | 200             |
| TC-19 | POST /api/auth/login (новый user)     | Роль отображается в JWT                | 200             |
| TC-20 | POST /api/auth/users/{id}/deactivate  | Деактивация пользователя               | 200             |
| TC-21 | GET /api/auth/organizations           | Список организаций                     | 200             |
| TC-22 | POST /api/auth/organizations          | Создание организации                   | 201             |
| TC-23 | POST /api/auth/organizations (дубль)  | Уникальность ИНН                       | 409             |
| TC-24 | GET /api/auth/projects                | Список проектов                        | 200             |
| TC-25 | POST /api/auth/projects (заказчик=подрядчик) | Бизнес-правило                  | 400             |
| TC-26 | POST /api/auth/projects               | Создание корректного проекта           | 201             |
| TC-27 | GET /.well-known/jwks.json            | Публичный ключ для других сервисов     | 200             |
| TC-28 | GET /internal/users/{id}              | Профиль без PII                        | 200             |
| TC-29 | GET /internal/users/{id}/permissions  | Права по проекту                       | 200             |
| TC-30 | GET /internal/users/{id} (без секрета)| Защита internal API                    | 403             |
| TC-31 | GET /api/auth/audit                   | Аудит-лог с метаданными                | 200             |
| TC-32 | GET /api/auth/audit?action=...        | Фильтрация аудита                      | 200             |
