# Тест-кейсы Workflow Service

**Swagger UI:** http://localhost:8004/docs  
**Среда:** локальная, Docker Compose (dev-режим — без Auth Service)

---

## Подготовка среды

### Шаг 1 — Запустить сервис в dev-режиме

```bash
cd part1/workflow-service
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### Шаг 2 — Сгенерировать тестовые токены

Сервис использует тот же механизм JWT, что и Catalog. Токены генерируются скриптом:

```bash
# PM заказчика
docker exec workflow-service python3 -c "
import jwt, time, uuid
pk = open('/app/jwt_public.pem').read()
# Для генерации нужен private key — он в tests/fixtures/jwt_private.pem
"
```

Проще — использовать токены из Catalog Service если он уже запущен в dev-режиме (тот же публичный ключ не подойдёт — у каждого сервиса свой ключ в fixtures/).

**Рекомендуемый способ:** запустить тесты `docker exec workflow-service pytest tests/ -v` — они покрывают все сценарии.

### Справочные данные

| Параметр | Значение |
|----------|----------|
| **PROJECT_ID** | `aaaaaaaa-0000-0000-0000-000000000001` |
| **INTERNAL_API_SECRET** | `internal_secret` |
| **Типы согласований** | `tz_final`, `nmck_final`, `review` |
| **Роли с правом binding-решения** | `pm` (approve/reject/revision) |
| **Роли с правом review** | `pm`, `analyst` |

---

## Блок 1 — Health

### TC-01: Сервис запущен и доступен

**Эндпоинт:** `GET /health`  
*(авторизация не нужна)*

**Ожидаемый результат:** `200 OK`
```json
{ "status": "ok", "db": "connected", "version": "1.0.0" }
```

---

## Блок 2 — Безопасность

### TC-02: Запрос без токена возвращает 401

**Эндпоинт:** `GET /api/workflow/approvals`

**Ожидаемый результат:** `401 Unauthorized`

---

### TC-03: Internal API без секрета возвращает 403

```bash
curl http://localhost:8004/internal/documents/some-doc/status
```

**Ожидаемый результат:** `403 Forbidden`

---

### TC-04: Документ без активного согласования — статус draft

```bash
curl http://localhost:8004/internal/documents/nonexistent-doc/status \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`
```json
{ "status": "draft", "locked": false }
```

---

## Блок 3 — Создание согласования

> Авторизоваться токеном **PM заказчика** (`side: customer`).

### TC-05: Отправить ТЗ на согласование (tz_final)

**Эндпоинт:** `POST /api/workflow/approvals`

**Тело запроса:**
```json
{
  "document_id": "doc-tz-001",
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "type": "tz_final"
}
```

**Ожидаемый результат:** `201 Created`
```json
{
  "id": "<approval_id>",
  "status": "pending",
  "type": "tz_final",
  "is_locked": true,
  "current_round": 1
}
```
**Сохранить:** `id` — понадобится в TC-06–16.

---

### TC-06: Документ заблокирован после отправки

```bash
curl http://localhost:8004/internal/documents/doc-tz-001/status \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`
```json
{ "status": "pending", "locked": true }
```

---

### TC-07: Нельзя создать второе tz_final на тот же документ

**Эндпоинт:** `POST /api/workflow/approvals`  
*(тело то же, что в TC-05)*

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "APPROVAL_EXISTS", "message": "An active non-review approval already exists for this document" } }
```

---

### TC-08: review-тип не блокирует документ

**Эндпоинт:** `POST /api/workflow/approvals`

**Тело запроса:**
```json
{
  "document_id": "doc-review-001",
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "type": "review"
}
```

**Ожидаемый результат:** `201 Created`, `is_locked: false`

---

## Блок 4 — Принятие решений

> Работаем с согласованием из TC-05.

### TC-09: Аналитик оставляет информационную рецензию

> Переключиться на токен **аналитика заказчика** (`role: analyst, side: customer`).

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`

**Тело запроса:**
```json
{ "decision": "review", "comment": "Раздел 4.2 требует уточнения требований к интеграции" }
```

**Ожидаемый результат:** `200 OK`, `status: "pending"`, `current_round: 1` — раунд не закрыт.

---

### TC-10: Аналитик не может принять binding-решение

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`  
*(токен аналитика)*

**Тело запроса:**
```json
{ "decision": "approve" }
```

**Ожидаемый результат:** `403 Forbidden`
```json
{ "error": { "code": "FORBIDDEN" } }
```

---

### TC-11: PM заказчика отправляет на доработку

> Переключиться на токен **PM заказчика**.

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`

**Тело запроса:**
```json
{ "decision": "revision", "comment": "Раздел 4.2: конкретизировать требования к производительности" }
```

**Ожидаемый результат:** `200 OK`, `status: "pending"` — ждём решения подрядчика.

---

### TC-12: Один пользователь не может решить дважды

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`  
*(токен PM заказчика снова)*

**Тело запроса:**
```json
{ "decision": "approve" }
```

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "ALREADY_DECIDED" } }
```

---

### TC-13: PM подрядчика подтверждает доработку → раунд 1 закрывается

> Переключиться на токен **PM подрядчика** (`role: pm, side: contractor`).

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`

**Тело запроса:**
```json
{ "decision": "revision", "comment": "Согласен, уточним требования" }
```

**Ожидаемый результат:** `200 OK`
```json
{
  "status": "revision",
  "is_locked": false,
  "current_round": 1
}
```

Документ разблокирован — можно редактировать в Catalog.

---

### TC-14: Повторная отправка открывает раунд 2

> PM заказчика решает «approve» после доработки.

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`  
*(токен PM заказчика)*

**Тело запроса:**
```json
{ "decision": "approve", "comment": "Доработали, одобряю" }
```

**Ожидаемый результат:** `200 OK`
```json
{
  "status": "pending",
  "current_round": 2,
  "is_locked": true
}
```

---

### TC-15: PM подрядчика одобряет → статус approved

> Переключиться на токен **PM подрядчика**.

**Эндпоинт:** `POST /api/workflow/approvals/{id}/decide`

**Тело запроса:**
```json
{ "decision": "approve" }
```

**Ожидаемый результат:** `200 OK`
```json
{
  "status": "approved",
  "current_round": 2,
  "is_locked": true
}
```

---

### TC-16: История содержит 2 раунда

**Эндпоинт:** `GET /api/workflow/approvals/{id}/history`

**Ожидаемый результат:** `200 OK`
```json
{
  "approval_id": "<id>",
  "rounds": [
    { "round_number": 1, "final_decision": "revision", "status": "completed" },
    { "round_number": 2, "final_decision": "approved", "status": "completed" }
  ]
}
```

---

## Блок 5 — Отзыв решения

### TC-17: PM может отозвать своё решение, пока раунд не закрыт

1. Создать новое согласование (`doc-revoke-001`): `POST /api/workflow/approvals`
2. PM заказчика решает `approve`
3. Отзывает решение:

**Эндпоинт:** `POST /api/workflow/approvals/{id}/revoke`  
*(токен PM заказчика)*

**Ожидаемый результат:** `200 OK`, `status: "pending"`

4. PM заказчика может снова принять решение:  
**Ожидаемый результат:** `200 OK`

---

### TC-18: Нельзя отозвать решение после закрытия раунда

> После TC-15 (оба РП одобрили) попытаться отозвать.

**Эндпоинт:** `POST /api/workflow/approvals/{id}/revoke`

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "ROUND_COMPLETED" } }
```

---

## Блок 6 — Отмена согласования

### TC-19: PM может отменить pending-согласование

1. Создать согласование (`doc-cancel-001`)
2. Отменить:

**Эндпоинт:** `POST /api/workflow/approvals/{id}/cancel`  
*(токен PM заказчика)*

**Ожидаемый результат:** `200 OK`
```json
{ "status": "cancelled", "is_locked": false }
```

**Проверка:** `GET /internal/documents/doc-cancel-001/status` → `{ "status": "draft", "locked": false }`

---

### TC-20: Нельзя отменить уже approved

> Попытаться отменить согласование из TC-15.

**Эндпоинт:** `POST /api/workflow/approvals/{id}/cancel`

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "CANNOT_CANCEL" } }
```

---

## Блок 7 — НМЦК (nmck_final)

### TC-21: Оба РП одобряют НМЦК в один раунд

1. PM заказчика создаёт: `POST /api/workflow/approvals` с `"type": "nmck_final"`, `document_id: "doc-nmck-001"`  
2. PM заказчика: `{ "decision": "approve" }` → `status: "pending"` (ждём подрядчика)  
3. PM подрядчика: `{ "decision": "approve" }` → `status: "approved"`

**Проверить:** `GET /internal/documents/doc-nmck-001/status` → `{ "locked": true, "status": "approved" }`

---

### TC-22: Аналитик не может принять решение по nmck_final

> Попытаться: `POST /api/workflow/approvals/{id}/decide`, `"decision": "review"` с токеном аналитика.

**Ожидаемый результат:** `403 Forbidden`  
*(nmck_final не допускает review-решений)*

---

## Блок 8 — Дашборд и задачи

### TC-23: Дашборд по проекту

**Эндпоинт:** `GET /api/workflow/dashboard?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Ожидаемый результат:** `200 OK`
```json
{ "pending": N, "approved": N, "rejected": N, "revision": N, "total": N }
```

---

### TC-24: Мои задачи

**Эндпоинт:** `GET /api/workflow/my-tasks?project_id=aaaaaaaa-0000-0000-0000-000000000001`

**Ожидаемый результат:** список согласований, где текущий пользователь ещё не принял решение.

---

## Блок 9 — Internal Audit

### TC-25: Аудит-лог за сессию

```bash
curl "http://localhost:8004/internal/audit?project_id=aaaaaaaa-0000-0000-0000-000000000001" \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`, массив с записями `approval.submit`, `approval.decide`, `approval.round_closed` и т.д.

---

## Сводная таблица

| № | Эндпоинт | Что проверяет | Ожидаемый статус |
|---|----------|---------------|-----------------|
| TC-01 | GET /health | Сервис и БД работают | 200 |
| TC-02 | GET /api/workflow/approvals (без токена) | 401 без авторизации | 401 |
| TC-03 | GET /internal/... (без секрета) | 403 без X-Internal-Secret | 403 |
| TC-04 | GET /internal/documents/.../status | draft если нет согласования | 200 |
| TC-05 | POST /api/workflow/approvals (tz_final) | Создание, is_locked=true | 201 |
| TC-06 | GET /internal/documents/.../status | Документ заблокирован | 200 |
| TC-07 | POST /api/workflow/approvals (дубль) | Нельзя создать второе | 409 |
| TC-08 | POST /api/workflow/approvals (review) | review не блокирует | 201 |
| TC-09 | POST .../decide (analyst, review) | Рецензия не закрывает раунд | 200 |
| TC-10 | POST .../decide (analyst, approve) | Аналитик не может approve | 403 |
| TC-11 | POST .../decide (pm customer, revision) | Ждём подрядчика | 200 |
| TC-12 | POST .../decide (pm customer снова) | Нельзя решить дважды | 409 |
| TC-13 | POST .../decide (pm contractor, revision) | Раунд 1 → revision | 200 |
| TC-14 | POST .../decide (pm customer, approve) | Открывается раунд 2 | 200 |
| TC-15 | POST .../decide (pm contractor, approve) | Статус → approved | 200 |
| TC-16 | GET .../history | 2 раунда в истории | 200 |
| TC-17 | POST .../revoke | Отзыв решения | 200 |
| TC-18 | POST .../revoke (после закрытия) | 409 раунд закрыт | 409 |
| TC-19 | POST .../cancel (pending) | Отмена, разблокировка | 200 |
| TC-20 | POST .../cancel (approved) | 409 нельзя отменить | 409 |
| TC-21 | nmck_final: approve + approve | approved за 1 раунд | 200 |
| TC-22 | nmck_final: analyst review | 403 нет рецензий в nmck | 403 |
| TC-23 | GET /api/workflow/dashboard | Сводка по статусам | 200 |
| TC-24 | GET /api/workflow/my-tasks | Мои ожидающие задачи | 200 |
| TC-25 | GET /internal/audit | Аудит-записи за сессию | 200 |
