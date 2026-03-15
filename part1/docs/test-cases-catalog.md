# Тест-кейсы Catalog Service

**Swagger UI:** http://localhost:8002/docs
**Среда:** локальная, Docker Compose (dev-режим — без Auth Service)

---

## Подготовка среды

### Шаг 1 — Запустить сервис в dev-режиме

```bash
cd part1/catalog-service
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Dev-режим отличается от продового одним: JWT верифицируется по локальному ключу (`JWT_PUBLIC_KEY_PATH`), а не через JWKS Auth Service. Всё остальное идентично.

---

### Шаг 2 — Сгенерировать тестовые токены

```bash
# PM (заказчик) — максимальные права
docker exec catalog-service python3 scripts/make_dev_token.py pm customer

# Администратор (подрядчик)
docker exec catalog-service python3 scripts/make_dev_token.py admin contractor

# Аналитик (заказчик)
docker exec catalog-service python3 scripts/make_dev_token.py analyst customer
```

Скрипт печатает токен в консоль. **Скопировать токен → открыть Swagger → кнопка Authorize → вставить.**

> **Важно:** первый запуск генерирует RSA-пару в Docker volume `catalog-dev-keys`.
> После перезапуска контейнера ключи сохраняются — токены остаются валидными.

---

### Справочные данные

| Параметр | Значение |
|----------|----------|
| **PROJECT_ID** | `aaaaaaaa-0000-0000-0000-000000000001` |
| **USER_ID** | `bbbbbbbb-0000-0000-0000-000000000001` |
| **Seed-шаблоны** | `tmpl-tz-001`, `tmpl-chtz-001`, `tmpl-pmi-001`, `tmpl-nmck-001` |
| **INTERNAL_API_SECRET** | `internal_secret` (из docker-compose.yml) |

---

## Блок 1 — Health

### TC-01: Сервис запущен и подключён к БД

**Эндпоинт:** `GET /health`
*(авторизация не нужна)*

**Ожидаемый результат:** `200 OK`
```json
{ "status": "ok", "db": "connected", "version": "1.0.0" }
```

---

## Блок 2 — Шаблоны

> Авторизоваться токеном **PM**.

### TC-02: Список системных шаблонов (без project_id)

**Эндпоинт:** `GET /api/catalog/templates`

**Ожидаемый результат:** `200 OK`, массив из 4 шаблонов (засеянных при старте)
```json
{
  "items": [
    { "id": "tmpl-tz-001",   "type": "tz",   "is_system": true },
    { "id": "tmpl-chtz-001", "type": "chtz", "is_system": true },
    { "id": "tmpl-pmi-001",  "type": "pmi",  "is_system": true },
    { "id": "tmpl-nmck-001", "type": "nmck", "output_format": "xlsx" }
  ],
  "total": 4
}
```

---

### TC-03: Запрос конкретного шаблона

**Эндпоинт:** `GET /api/catalog/templates/tmpl-tz-001`

**Ожидаемый результат:** `200 OK`, полный объект с массивом `sections` (должно быть 10 разделов).
**Проверить:** поле `formatting.font` = `"Times New Roman"`.

---

### TC-04: Фильтр по типу

**Эндпоинт:** `GET /api/catalog/templates?type=nmck`

**Ожидаемый результат:** `200 OK`, `total: 1`, единственный шаблон с `output_format: "xlsx"`.

---

### TC-05: Создать пользовательский шаблон (форк ТЗ)

**Эндпоинт:** `POST /api/catalog/templates`

**Тело запроса:**
```json
{
  "type": "tz",
  "name": "ТЗ для ГИС ЖКХ (кастомный)",
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "parent_id": "tmpl-tz-001",
  "sections": []
}
```

**Ожидаемый результат:** `201 Created`
```json
{ "id": "<uuid>", "is_system": false, "parent_id": "tmpl-tz-001", "version": 1 }
```
**Сохранить:** `id` шаблона — понадобится в TC-06, TC-07, TC-27.

---

### TC-06: Обновить шаблон (новая версия)

**Эндпоинт:** `PUT /api/catalog/templates/{id}` *(id из TC-05)*

**Тело запроса:**
```json
{ "name": "ТЗ для ГИС ЖКХ v2" }
```

**Ожидаемый результат:** `200 OK`, `version: 2`, `name` обновлён.

---

### TC-07: Аналитик не может создать шаблон

> Переключиться на токен **Аналитика**.

**Эндпоинт:** `POST /api/catalog/templates`

**Тело запроса:**
```json
{
  "type": "chtz",
  "name": "Попытка аналитика",
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "sections": []
}
```

**Ожидаемый результат:** `403 Forbidden`
```json
{ "error": { "code": "FORBIDDEN", "message": "Insufficient permissions" } }
```

---

### TC-08: Нельзя удалить системный шаблон

> Переключиться на токен **PM**.

**Эндпоинт:** `DELETE /api/catalog/templates/tmpl-tz-001`

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "SYSTEM_TEMPLATE", "message": "Cannot delete system template" } }
```

---

### TC-09: Удалить пользовательский шаблон

**Эндпоинт:** `DELETE /api/catalog/templates/{id}` *(id из TC-05)*

**Ожидаемый результат:** `204 No Content`
**Проверка:** `GET /api/catalog/templates/{id}` → `404 Not Found`.

---

## Блок 3 — Подсистемы

> Авторизоваться токеном **PM**.

### TC-10: Создать подсистему

**Эндпоинт:** `POST /api/catalog/subsystems`

**Тело запроса:**
```json
{
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "code": "ПБ",
  "name": "Подсистема информационной безопасности",
  "description": "Обеспечивает защиту информации",
  "order": 1,
  "tz_section_prefix": "4.2"
}
```

**Ожидаемый результат:** `201 Created`, объект с `id`.
**Сохранить:** `id` подсистемы — понадобится в TC-11–14.

---

### TC-11: Создать вторую подсистему

**Эндпоинт:** `POST /api/catalog/subsystems`

**Тело запроса:**
```json
{
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "code": "АДМ",
  "name": "Подсистема администрирования",
  "order": 2
}
```

**Ожидаемый результат:** `201 Created`.
**Сохранить:** `id` второй подсистемы.

---

### TC-12: Список подсистем отсортирован по order

**Эндпоинт:** `GET /api/catalog/subsystems?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Ожидаемый результат:** `200 OK`, `total: 2`, первой идёт "ПБ" (order=1), второй "АДМ" (order=2).

---

### TC-13: Изменить порядок подсистем

**Эндпоинт:** `PUT /api/catalog/subsystems/reorder?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Тело запроса:** *(id второй подсистемы первым)*
```json
{ "ids": ["<id_АДМ>", "<id_ПБ>"] }
```

**Ожидаемый результат:** `200 OK`
**Проверка:** повторить TC-12 — порядок изменился ("АДМ" теперь первая).

---

### TC-14: Нельзя удалить подсистему с функциями

> Сначала создать функцию в этой подсистеме (TC-16), затем вернуться к этому тесту.

**Эндпоинт:** `DELETE /api/catalog/subsystems/{id_ПБ}`

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "HAS_FUNCTIONS", "message": "Cannot delete subsystem with active functions" } }
```

---

### TC-15: Аналитик не может удалить подсистему

> Переключиться на токен **Аналитика**.

**Эндпоинт:** `DELETE /api/catalog/subsystems/{id_ПБ}`

**Ожидаемый результат:** `403 Forbidden`

---

## Блок 4 — Справочник функций

> Авторизоваться токеном **PM**.

### TC-16: Создать функцию

**Эндпоинт:** `POST /api/catalog/functions`

**Тело запроса:**
```json
{
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "subsystem_id": "<id_ПБ>",
  "code": "ФБ-01",
  "name": "Аутентификация пользователей",
  "category": "security",
  "priority": "must",
  "complexity": "medium",
  "description": "Система должна обеспечивать многофакторную аутентификацию.",
  "requirements": [
    { "id": "REQ-01-01", "text": "Система должна поддерживать вход по логину и паролю", "type": "functional" },
    { "id": "REQ-01-02", "text": "Пароль должен соответствовать политике безопасности", "type": "functional" }
  ],
  "cost_params": { "labor_hours": 40, "rate_per_hour": 3500, "complexity_coeff": 1.2 },
  "tags": ["auth", "security"]
}
```

**Ожидаемый результат:** `201 Created`, `status: "draft"`, `version: 1`.
**Сохранить:** `id` функции — понадобится в TC-17–23.

---

### TC-17: Создать вторую функцию (аналитиком)

> Переключиться на токен **Аналитика**.

**Эндпоинт:** `POST /api/catalog/functions`

**Тело запроса:**
```json
{
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "code": "ФБ-02",
  "name": "Журналирование действий",
  "category": "security",
  "priority": "should",
  "description": "Система должна вести журнал всех действий пользователей."
}
```

**Ожидаемый результат:** `201 Created` (аналитик имеет право создавать функции).

---

### TC-18: Список функций с фильтром по подсистеме

> Можно остаться с токеном Аналитика.

**Эндпоинт:** `GET /api/catalog/functions?project_id=aaaaaaaa-0000-0000-0000-000000000001&subsystem_id={id_ПБ}`

**Ожидаемый результат:** `200 OK`, только функции, привязанные к подсистеме "ПБ".

---

### TC-19: Поиск функции по ключевому слову

**Эндпоинт:** `GET /api/catalog/functions?project_id=aaaaaaaa-0000-0000-0000-000000000001&q=аутентификация`

**Ожидаемый результат:** `200 OK`, в результате функция ФБ-01.

---

### TC-20: Аналитик редактирует описание функции

> Токен **Аналитика**.

**Эндпоинт:** `PUT /api/catalog/functions/{id}` *(id из TC-16)*

**Тело запроса:**
```json
{ "description": "Обновлённое описание аналитиком." }
```

**Ожидаемый результат:** `200 OK`, `version: 2`.

---

### TC-21: Аналитик НЕ может изменить стоимостные параметры

**Эндпоинт:** `PUT /api/catalog/functions/{id}` *(токен Аналитика)*

**Тело запроса:**
```json
{ "cost_params": { "labor_hours": 999 } }
```

**Ожидаемый результат:** `403 Forbidden`
```json
{ "error": { "code": "FORBIDDEN", "message": "Only pm can edit cost and priority fields" } }
```

---

### TC-22: PM изменяет стоимостные параметры и приоритет

> Переключиться на токен **PM**.

**Эндпоинт:** `PUT /api/catalog/functions/{id}`

**Тело запроса:**
```json
{
  "priority": "must",
  "complexity": "high",
  "cost_params": { "labor_hours": 80, "rate_per_hour": 4000, "complexity_coeff": 1.5 }
}
```

**Ожидаемый результат:** `200 OK`, все три поля обновлены.

---

### TC-23: Мягкое удаление функции

**Эндпоинт:** `DELETE /api/catalog/functions/{id}` *(id ФБ-02 из TC-17)*

**Ожидаемый результат:** `204 No Content`
**Проверка 1:** `GET /api/catalog/functions/{id}` → `404 Not Found`
**Проверка 2:** функция не появляется в списке `GET /api/catalog/functions?project_id=...`
**Проверка 3:** документ БД содержит запись с `status: "deleted"` (мягкое удаление, не физическое).

---

## Блок 5 — Ставки

> Авторизоваться токеном **PM**.

### TC-24: Установить ставки для проекта

**Эндпоинт:** `PUT /api/catalog/rates/aaaaaaaa-0000-0000-0000-000000000001`

**Тело запроса:**
```json
{
  "default_rate_per_hour": 3500,
  "complexity_coefficients": { "low": 1.0, "medium": 1.2, "high": 1.5, "critical": 2.0 },
  "overhead_coefficient": 1.15,
  "vat_rate": 0.20,
  "profit_margin": 0.15
}
```

**Ожидаемый результат:** `200 OK`, все поля сохранены.

---

### TC-25: Получить ставки

**Эндпоинт:** `GET /api/catalog/rates?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Ожидаемый результат:** `200 OK`, данные совпадают с установленными в TC-24.

---

### TC-26: Аналитик не может изменить ставки

> Переключиться на токен **Аналитика**.

**Эндпоинт:** `PUT /api/catalog/rates/aaaaaaaa-0000-0000-0000-000000000001`

**Тело запроса:**
```json
{ "default_rate_per_hour": 1 }
```

**Ожидаемый результат:** `403 Forbidden`

---

## Блок 6 — Документы

> Авторизоваться токеном **PM**.

### TC-27: Создать документ из шаблона

**Эндпоинт:** `POST /api/catalog/documents`

**Тело запроса:**
```json
{
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "template_id": "tmpl-tz-001",
  "name": "ТЗ на ГИС ЖКХ v1",
  "type": "tz",
  "function_ids": ["<id_ФБ-01>"],
  "data": {
    "sections": {
      "1": {
        "system_name": "ГИС ЖКХ",
        "customer_name": "Минстрой России"
      }
    }
  }
}
```

**Ожидаемый результат:** `201 Created`, `status: "draft"`, `version: 1`.
**Сохранить:** `id` документа — понадобится в TC-28–34.

---

### TC-28: Список документов проекта

**Эндпоинт:** `GET /api/catalog/documents?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Ожидаемый результат:** `200 OK`, минимум 1 документ.

---

### TC-29: Получить документ

**Эндпоинт:** `GET /api/catalog/documents/{id}`

**Ожидаемый результат:** `200 OK`, полный объект, `data.sections.1.system_name = "ГИС ЖКХ"`.

---

### TC-30: Обновить данные документа

**Эндпоинт:** `PUT /api/catalog/documents/{id}`

**Тело запроса:**
```json
{
  "data": {
    "sections": {
      "1": {
        "system_name": "ГИС ЖКХ",
        "customer_name": "Минстрой России",
        "contractor_name": "ООО СофтДев"
      },
      "4.3": {
        "software_req": "Astra Linux SE 1.7",
        "hardware_req": "Сервер: 8 CPU, 32 GB RAM"
      }
    }
  }
}
```

**Ожидаемый результат:** `200 OK`, `version: 2`.

---

### TC-31: Аналитик может редактировать черновик

> Переключиться на токен **Аналитика**.

**Эндпоинт:** `PUT /api/catalog/documents/{id}`

**Тело запроса:**
```json
{ "name": "ТЗ на ГИС ЖКХ — обновлено аналитиком" }
```

**Ожидаемый результат:** `200 OK` (у аналитика есть `document.edit` на черновики).

---

### TC-32: Валидация документа — есть ошибки

> Переключиться на токен **PM**.

**Эндпоинт:** `POST /api/catalog/documents/{id}/validate`

*(Документ не заполнен полностью — нет обязательных полей некоторых разделов)*

**Ожидаемый результат:** `200 OK`
```json
{
  "is_valid": false,
  "errors": ["section.1.system_name: required"],
  "warnings": ["section.4.2: 0 functions"]
}
```

---

### TC-33: Заблокированный документ нельзя редактировать

Изменить `status` документа на `pending` напрямую через MongoDB (или через будущий Workflow Service) и затем попробовать обновить:

**Эндпоинт:** `PUT /api/catalog/documents/{id}`

**Тело запроса:**
```json
{ "name": "Попытка изменить" }
```

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "DOCUMENT_LOCKED", "message": "Document is locked (status: pending)" } }
```

---

### TC-34: Аналитик не может удалить документ

> Токен **Аналитика**.

**Эндпоинт:** `DELETE /api/catalog/documents/{id}`

**Ожидаемый результат:** `403 Forbidden`

---

### TC-35: PM удаляет документ

> Переключиться на токен **PM**.

**Эндпоинт:** `DELETE /api/catalog/documents/{id}`

**Ожидаемый результат:** `204 No Content`
**Проверка:** `GET /api/catalog/documents/{id}` → `404 Not Found`

---

## Блок 7 — Internal API

> Запросы через `curl` — эти эндпоинты недоступны в Swagger напрямую (нет поля для заголовка `X-Internal-Secret`).

### TC-36: Render-bundle без секрета возвращает 403

```bash
curl http://localhost:8002/internal/documents/<id>/render-bundle
```

**Ожидаемый результат:** `403 Forbidden`

---

### TC-37: Render-bundle с секретом

*(Предварительно создать документ по TC-27, не удалять)*

```bash
curl http://localhost:8002/internal/documents/<id>/render-bundle \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`
```json
{
  "template": { "sections": [...], "formatting": {...} },
  "dotx_key": "templates/dotx-gost34-tz.dotx",
  "data": { "sections": { "1": {...} } },
  "functions": [{ "id": "...", "code": "ФБ-01", ... }],
  "subsystems": [...],
  "rates": { "default_rate_per_hour": 3500, ... },
  "project": { "id": "aaaaaaaa-0000-0000-0000-000000000001" }
}
```

---

### TC-38: Render-bundle — документ не найден

```bash
curl http://localhost:8002/internal/documents/nonexistent-id/render-bundle \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `404 Not Found`

---

### TC-39: Internal audit — список записей

```bash
curl "http://localhost:8002/internal/audit" \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`, массив записей аудита, накопленных за время тестирования.
**Проверить наличие полей:** `action`, `resource_type`, `resource_id`, `user_id`, `timestamp`, `result`.

---

### TC-40: Internal audit — фильтр по проекту

```bash
curl "http://localhost:8002/internal/audit?project_id=aaaaaaaa-0000-0000-0000-000000000001" \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`, только записи этого проекта.

---

## Блок 8 — Безопасность

### TC-41: Запрос без токена возвращает 401

**Эндпоинт:** `GET /api/catalog/templates` *(без Authorize)*

**Ожидаемый результат:** `401 Unauthorized`
```json
{ "detail": { "code": "UNAUTHORIZED", "message": "Missing or invalid Authorization header" } }
```

---

### TC-42: Просроченный / невалидный токен

**Эндпоинт:** `GET /api/catalog/templates`
**Заголовок:** `Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature`

**Ожидаемый результат:** `401 Unauthorized`
```json
{ "detail": { "code": "INVALID_TOKEN", "message": "Invalid or expired token" } }
```

---

### TC-43: Пользователь из другого проекта не получает доступ на запись

Сгенерировать токен PM для **другого** проекта:
```bash
# Скрипт использует PROJECT_ID из env-переменной
docker exec catalog-service python3 -c "
import jwt, time
pk = open('/keys/jwt_private.pem').read()
token = jwt.encode({
    'sub': 'dddddddd-0000-0000-0000-000000000001',
    'org_id': 'cccccccc-0000-0000-0000-000000000001',
    'roles': [{'project_id': 'ffffffff-0000-0000-0000-000000000001', 'role': 'pm', 'side': 'customer'}],
    'is_superadmin': False,
    'iat': int(time.time()), 'exp': int(time.time()) + 3600
}, pk, algorithm='RS256')
print(token)
"
```

**Эндпоинт:** `POST /api/catalog/functions`
**Тело:** с `project_id: "aaaaaaaa-0000-0000-0000-000000000001"`

**Ожидаемый результат:** `403 Forbidden`

---

## Сводная таблица

| №     | Эндпоинт                                        | Что проверяет                                 | Ожидаемый статус |
|-------|-------------------------------------------------|-----------------------------------------------|-----------------|
| TC-01 | GET /health                                     | Сервис и БД работают                          | 200             |
| TC-02 | GET /api/catalog/templates                      | Список seed-шаблонов                          | 200             |
| TC-03 | GET /api/catalog/templates/tmpl-tz-001          | Получение шаблона с разделами                 | 200             |
| TC-04 | GET /api/catalog/templates?type=nmck            | Фильтр по типу                                | 200             |
| TC-05 | POST /api/catalog/templates                     | Создание пользовательского шаблона (PM)       | 201             |
| TC-06 | PUT /api/catalog/templates/{id}                 | Обновление, версия инкрементируется           | 200             |
| TC-07 | POST /api/catalog/templates (аналитик)          | Аналитик не может создавать шаблоны           | 403             |
| TC-08 | DELETE /api/catalog/templates/tmpl-tz-001       | Системный шаблон нельзя удалить               | 409             |
| TC-09 | DELETE /api/catalog/templates/{id}              | Удаление пользовательского шаблона            | 204             |
| TC-10 | POST /api/catalog/subsystems                    | Создание подсистемы                           | 201             |
| TC-11 | POST /api/catalog/subsystems                    | Создание второй подсистемы                    | 201             |
| TC-12 | GET /api/catalog/subsystems                     | Список отсортирован по order                  | 200             |
| TC-13 | PUT /api/catalog/subsystems/reorder             | Изменение порядка подсистем                   | 200             |
| TC-14 | DELETE /api/catalog/subsystems/{id}             | Нельзя удалить подсистему с функциями         | 409             |
| TC-15 | DELETE /api/catalog/subsystems/{id} (аналитик) | Аналитик не может удалять подсистемы          | 403             |
| TC-16 | POST /api/catalog/functions (PM)                | Создание функции с cost_params                | 201             |
| TC-17 | POST /api/catalog/functions (аналитик)          | Аналитик может создавать функции              | 201             |
| TC-18 | GET /api/catalog/functions?subsystem_id=...     | Фильтр по подсистеме                          | 200             |
| TC-19 | GET /api/catalog/functions?q=...                | Полнотекстовый поиск                          | 200             |
| TC-20 | PUT /api/catalog/functions/{id} (аналитик)      | Аналитик редактирует описание                 | 200             |
| TC-21 | PUT /api/catalog/functions/{id} (аналитик)      | Аналитик не редактирует cost_params           | 403             |
| TC-22 | PUT /api/catalog/functions/{id} (PM)            | PM редактирует cost_params и priority         | 200             |
| TC-23 | DELETE /api/catalog/functions/{id}              | Мягкое удаление, функция скрыта из списка     | 204             |
| TC-24 | PUT /api/catalog/rates/{project_id}             | Установить ставки                             | 200             |
| TC-25 | GET /api/catalog/rates                          | Получить ставки                               | 200             |
| TC-26 | PUT /api/catalog/rates/{id} (аналитик)          | Аналитик не может менять ставки               | 403             |
| TC-27 | POST /api/catalog/documents                     | Создание документа из шаблона                 | 201             |
| TC-28 | GET /api/catalog/documents                      | Список документов проекта                     | 200             |
| TC-29 | GET /api/catalog/documents/{id}                 | Получение документа с данными                 | 200             |
| TC-30 | PUT /api/catalog/documents/{id} (PM)            | Обновление данных, версия растёт              | 200             |
| TC-31 | PUT /api/catalog/documents/{id} (аналитик)      | Аналитик редактирует черновик                 | 200             |
| TC-32 | POST /api/catalog/documents/{id}/validate       | Валидация: ошибки и предупреждения            | 200             |
| TC-33 | PUT /api/catalog/documents/{id} (pending)       | Заблокированный документ нельзя редактировать | 409             |
| TC-34 | DELETE /api/catalog/documents/{id} (аналитик)   | Аналитик не удаляет документы                 | 403             |
| TC-35 | DELETE /api/catalog/documents/{id} (PM)         | PM удаляет документ                           | 204             |
| TC-36 | GET /internal/.../render-bundle (без секрета)   | Защита internal API                           | 403             |
| TC-37 | GET /internal/.../render-bundle                 | Полный render-bundle для Generation Service   | 200             |
| TC-38 | GET /internal/.../render-bundle (несуществующий)| 404 для несуществующего документа             | 404             |
| TC-39 | GET /internal/audit                             | Аудит-записи за сессию                        | 200             |
| TC-40 | GET /internal/audit?project_id=...              | Фильтрация аудита                             | 200             |
| TC-41 | GET /api/catalog/templates (без токена)         | 401 без авторизации                           | 401             |
| TC-42 | GET /api/catalog/templates (невалидный токен)   | 401 на невалидный токен                       | 401             |
| TC-43 | POST /api/catalog/functions (чужой проект)      | 403 — нет роли в проекте                      | 403             |
