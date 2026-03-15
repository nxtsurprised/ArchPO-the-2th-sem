# Catalog Service — интерфейс взаимодействия с Workflow Service

Этот документ описывает, что Catalog ожидает от Workflow Service, и что Workflow ожидает от Catalog.

---

## 1. Что Catalog ожидает от Workflow

### 1.1 Смена статуса документа

Catalog не меняет `document.status` самостоятельно. Workflow Service должен уведомить Catalog об изменении статуса через internal API.

**Предлагаемый контракт:**

```
PATCH /internal/documents/:id/status
X-Internal-Secret: <INTERNAL_API_SECRET>
Content-Type: application/json

{
  "status": "pending" | "approved" | "rejected" | "draft",
  "locked": true | false
}
```

**Поведение Catalog после получения:**
- Сохраняет новый `status` в документе.
- Если `status ∈ {pending, approved}` → документ блокируется (PUT возвращает 409).
- Если `status = draft` или `rejected` → блокировка снимается.

**Текущая реализация:** эндпоинт не существует. Статус меняется напрямую в MongoDB или через будущий Workflow Service.

---

### 1.2 Какие статусы документа существуют

| Статус    | Описание                                        | Редактирование |
|-----------|-------------------------------------------------|----------------|
| `draft`   | Черновик, свободно редактируется                | Разрешено      |
| `pending` | Отправлен на согласование, заблокирован         | **Запрещено (409)** |
| `approved`| Утверждён, заблокирован                         | **Запрещено (409)** |
| `rejected`| Отклонён, возвращён в работу                    | Разрешено      |

---

## 2. Что Workflow ожидает от Catalog

### 2.1 Render-bundle для рендера документа

Перед генерацией файла Generation Service запрашивает Catalog:

```
GET /internal/documents/:id/render-bundle
X-Internal-Secret: <INTERNAL_API_SECRET>
```

**Ответ (200 OK):**
```json
{
  "template":   { "sections": [...], "formatting": {...} },
  "dotx_key":   "templates/dotx-gost34-tz.dotx",
  "data":       { "sections": { "1": {...}, "4.3": {...} } },
  "functions":  [ { "id": "...", "code": "ФБ-01", "name": "...", ... } ],
  "subsystems": [ { "id": "...", "code": "ПБ", "order": 1, ... } ],
  "rates":      { "default_rate_per_hour": 3500, "vat_rate": 0.20, ... },
  "project":    { "id": "aaaaaaaa-0000-0000-0000-000000000001" }
}
```

Подробный пример: [render-bundle-example.json](render-bundle-example.json)

### 2.2 Получение документа

```
GET /api/catalog/documents/:id
Authorization: Bearer <access_token>
```

Workflow использует для проверки текущего статуса перед созданием раунда согласования.

### 2.3 Список функций проекта

```
GET /api/catalog/functions?project_id=:id
Authorization: Bearer <access_token>
```

Workflow может запрашивать список функций при формировании объёма работ для согласования.

---

## 3. Sequence: жизненный цикл документа

```
[PM] POST /api/catalog/documents           → status: draft
[PM] PUT  /api/catalog/documents/:id       → редактирование (пока draft)
[PM] POST /api/catalog/documents/:id/validate → проверка полноты

[PM] POST /api/workflow/requests           → создаёт запрос на согласование
  └─► Workflow: PATCH /internal/documents/:id/status { "status": "pending" }
      → Catalog блокирует документ (PUT → 409)

[PM+Contractor] решения в Workflow...

[Workflow] раунд завершён → approve
  └─► Workflow: PATCH /internal/documents/:id/status { "status": "approved" }
  └─► Workflow → Generation: GET /internal/documents/:id/render-bundle
      → Generation рендерит .docx / .xlsx, сохраняет в MinIO

[PM] отклонён → revision
  └─► Workflow: PATCH /internal/documents/:id/status { "status": "draft" }
      → Catalog разблокирует документ
```

---

## 4. Аутентификация между сервисами

| Тип запроса | Метод аутентификации |
|-------------|---------------------|
| Workflow → Catalog (status update) | `X-Internal-Secret` заголовок |
| Generation → Catalog (render-bundle) | `X-Internal-Secret` заголовок |
| Workflow → Catalog (чтение документов) | `Bearer` JWT (service-account токен) |

`INTERNAL_API_SECRET` задаётся через `docker-compose.yml`:
```
INTERNAL_API_SECRET: ${INTERNAL_API_SECRET:-internal_secret}
```
В production — из Vault/Secrets Manager.

---

## 5. Nginx: блокировка /internal извне

```nginx
location /internal/ {
    deny all;
}
```

`/internal/*` эндпоинты недоступны из интернета — только из внутренней Docker-сети (`catalog-net`).
