# Catalog Service — Спецификация

## Обзор

Хранение и управление шаблонами документов, справочником функций, подсистемами, ставками и заполненными данными документов. MongoDB. Центральный сервис данных — Generation и Workflow зависят от него.

**БД:** MongoDB 7 CE  
**ODM:** Motor / Beanie  
**Порт:** 8002

## Модель данных (6 коллекций + audit_log)

### templates
```json
{
  "_id": "tmpl-tz-001",
  "type": "tz",                          // tz | chtz | pmi | nmck
  "name": "Техническое задание (ГОСТ 34.602-2020)",
  "gost_ref": "ГОСТ 34.602-2020",
  "output_format": "docx",               // docx | xlsx
  "is_system": true,                      // базовый, нельзя удалить
  "parent_id": null,                      // ссылка на оригинал при форке
  "project_id": null,                     // null = общесистемный
  "dotx_file_key": "templates/dotx-gost34-v1.dotx",  // путь в MinIO
  "formatting": {
    "font": "Times New Roman", "font_size": 14,
    "margins": { "top": 20, "bottom": 20, "left": 30, "right": 15 },
    "line_spacing": 1.5, "gost_ref": "ГОСТ 2.105-2019"
  },
  "sections": [
    {
      "number": "1", "title": "Общие сведения",
      "source": "manual",
      "fields": [
        { "key": "system_name", "label": "Полное наименование системы", "type": "text", "required": true },
        { "key": "customer_name", "label": "Заказчик", "type": "text", "required": true },
        { "key": "contractor_name", "label": "Исполнитель", "type": "text" },
        { "key": "contract_basis", "label": "Основание для разработки", "type": "textarea" },
        { "key": "deadlines", "label": "Плановые сроки", "type": "date_range" }
      ]
    },
    {
      "number": "4.2", "title": "Требования к функциям (задачам)",
      "source": "functions",
      "render_rule": "functions_grouped_by_subsystem",
      "function_template": {
        "heading": "{{function.code}} {{function.name}}",
        "body": "{{function.description}}",
        "requirements_list": "{{function.requirements}}"
      }
    },
    {
      "number": "7", "title": "Требования к документированию",
      "source": "static",
      "static_content": "Документация на систему должна быть выполнена в соответствии с ГОСТ 2.105..."
    }
  ],
  "version": 1,
  "created_by": "system",
  "created_at": "...", "updated_at": "..."
}
```

Типы source: `manual` (пользователь заполняет поля), `functions` (автогенерация из справочника), `subsystems` (перечень подсистем), `static` (фиксированный текст).

Типы полей: `text`, `textarea`, `richtext`, `list`, `date_range`.

### functions
```json
{
  "_id": "func-0042",
  "project_id": "proj-001",
  "subsystem_id": "subsys-001",
  "code": "ФБ-03",                       // человекочитаемый шифр
  "name": "Журналирование действий пользователей",
  "category": "security",                 // enum: security, data_management, reporting, integration, ui, administration
  "priority": "must",                     // enum: must, should, could, wont (MoSCoW)
  "status": "active",                     // draft, active, deprecated, deleted
  "description": "Система должна обеспечивать...",
  "requirements": [
    { "id": "REQ-042-01", "text": "Система должна фиксировать...", "type": "functional" }
  ],
  "input_data": "Действия пользователя в интерфейсе",
  "output_data": "Запись в журнале аудита",
  "constraints": "Время записи не более 100 мс",
  "dependencies": ["func-0010"],
  "complexity": "medium",
  "cost_params": {
    "labor_hours": 40,
    "rate_per_hour": 3500,                // может переопределяться из rates
    "complexity_coeff": 1.2,
    "overhead_coeff": 1.15
    // total НЕ хранится — вычисляется
  },
  "test_params": {
    "approach": "manual",                 // manual, automated, mixed
    "criteria": [
      { "id": "AC-01", "text": "Все действия записываются в журнал" }
    ],
    "test_data": "Тестовый пользователь с ролью аналитик",
    "expected_result": "Запись в audit_log с корректными полями"
  },
  "doc_refs": {
    "tz_section": "4.2.1",
    "chtz_section": "3.1",
    "pmi_test_ids": ["test-012"],
    "nmck_row": null
  },
  "tags": ["audit", "security", "logging"],
  "created_by": "user-uuid",
  "version": 1,
  "created_at": "...", "updated_at": "..."
}
```

### subsystems
```json
{
  "_id": "subsys-001",
  "project_id": "proj-001",
  "code": "ПБ",
  "name": "Подсистема информационной безопасности",
  "description": "Обеспечивает защиту информации...",
  "order": 1,
  "tz_section_prefix": "4.2",
  "created_at": "...", "updated_at": "..."
}
```

### rates
```json
{
  "_id": "rates-proj-001",
  "project_id": "proj-001",
  "default_rate_per_hour": 3500,
  "complexity_coefficients": {
    "low": 1.0, "medium": 1.2, "high": 1.5, "critical": 2.0
  },
  "overhead_coefficient": 1.15,
  "vat_rate": 0.20,
  "profit_margin": 0.15,
  "updated_by": "user-uuid",
  "updated_at": "..."
}
```

### documents
```json
{
  "_id": "doc-tz-001",
  "project_id": "proj-001",
  "template_id": "tmpl-tz-001",
  "name": "ТЗ на ГИС ЖКХ v1",
  "type": "tz",
  "status": "draft",
  "locked": false,
  "function_ids": ["func-0042", "func-0043"],
  "data": {
    "sections": {
      "1": {
        "system_name": "ГИС ЖКХ",
        "customer_name": "Минстрой России"
      },
      "4.3": {
        "software_req": "Astra Linux SE 1.7...",
        "hardware_req": "Сервер: 8 CPU, 32 GB RAM..."
      }
    }
  },
  "version": 1,
  "created_by": "user-uuid",
  "created_at": "...",
  "updated_at": "...",
  "archived": false,
  "archived_at": null,
  "archive_key": null
}
```

Поля холодного хранилища:

| Поле | Тип | Описание |
|------|-----|---------|
| `archived` | bool | `true` — файл перенесён в `documents-archive` bucket |
| `archived_at` | string\|null | ISO datetime архивирования |
| `archive_key` | string\|null | Ключ объекта в MinIO `documents-archive` bucket |

`locked` выставляется Kafka-консьюмером при получении событий `document.locked` / `document.unlocked` от workflow-service.

### audit_log (MongoDB коллекция)
Та же структура, что в Auth (см. shared AuditEntry). service = "catalog".

## API-эндпоинты

### Шаблоны
| Метод | Путь | Роли | Описание |
|-------|------|------|----------|
| GET | `/api/catalog/templates?project_id=&type=` | все | Список шаблонов |
| GET | `/api/catalog/templates/:id` | все | Полный шаблон с JSON-схемой |
| POST | `/api/catalog/templates` | pm, admin | Создание (или форк базового) |
| PUT | `/api/catalog/templates/:id` | pm, admin | Обновление (новая версия) |
| DELETE | `/api/catalog/templates/:id` | pm | Удаление (запрещено для is_system) |

### Справочник функций
| Метод | Путь | Роли | Описание |
|-------|------|------|----------|
| GET | `/api/catalog/functions?project_id=&category=&subsystem_id=&q=` | все | Список с фильтрами и поиском |
| GET | `/api/catalog/functions/:id` | все | Детали функции (все 4 блока) |
| POST | `/api/catalog/functions` | pm, analyst | Создание |
| PUT | `/api/catalog/functions/:id` | pm, analyst (info); pm (cost, priority) | Обновление. cost_params — только pm |
| DELETE | `/api/catalog/functions/:id` | pm | Soft delete. 409 если привязана к согласованному документу |

### Подсистемы
| Метод | Путь | Роли | Описание |
|-------|------|------|----------|
| GET | `/api/catalog/subsystems?project_id=` | все | Список (отсортирован по order) |
| POST | `/api/catalog/subsystems` | pm | Создание |
| PUT | `/api/catalog/subsystems/:id` | pm | Обновление |
| PUT | `/api/catalog/subsystems/reorder` | pm | Изменение порядка |
| DELETE | `/api/catalog/subsystems/:id` | pm | Удаление (409 если есть функции) |

### Ставки
| Метод | Путь | Роли | Описание |
|-------|------|------|----------|
| GET | `/api/catalog/rates?project_id=` | все | Справочник ставок проекта |
| PUT | `/api/catalog/rates/:project_id` | pm | Обновление |

### Документы
| Метод | Путь | Роли | Описание |
|-------|------|------|----------|
| GET | `/api/catalog/documents?project_id=&type=` | все | Список документов |
| GET | `/api/catalog/documents/:id` | все | Заполненные данные |
| POST | `/api/catalog/documents` | pm, admin | Создание из шаблона |
| PUT | `/api/catalog/documents/:id` | все (если draft/revision) | Обновление данных. 409 если locked (pending/approved) |
| DELETE | `/api/catalog/documents/:id` | pm | Удаление |

### Internal API
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/internal/documents/:id/render-bundle` | Всё для генерации: template + data + functions + subsystems + rates + project info |
| GET | `/internal/documents/archivable?days=90&limit=100` | Документы готовые к архивированию (approved/rejected, старше N дней, не архивированы) |
| PATCH | `/internal/documents/:id/archive` | Пометить документ архивированным (`archived=true`, `archive_key`, `archived_at`) |
| GET | `/internal/pmi-functions?project_id=` | Функции проекта для PMI-агента |
| PUT | `/internal/documents/:id/pmi-results` | Сохранить результаты PMI-агента |
| GET | `/internal/tz-context?project_id=` | Текст ТЗ/ЧТЗ для PMI-агента |
| GET | `/internal/audit` | Аудит-записи для агрегации Auth |

Все internal endpoints защищены заголовком `X-Internal-Secret`. Nginx блокирует `/internal/*` снаружи.

### Render-bundle формат
```json
{
  "template": { "sections": [...], "formatting": {...} },
  "dotx_key": "templates/dotx-gost34-v1.dotx",
  "data": { "sections": { "1": {...}, "4.3": {...} } },
  "functions": [{ "_id": "func-0042", "code": "ФБ-03", ... }],
  "subsystems": [{ "_id": "subsys-001", "code": "ПБ", "order": 1, ... }],
  "rates": { "default_rate_per_hour": 3500, "complexity_coefficients": {...} },
  "project": { "name": "ГИС ЖКХ", "code": "GIS-ZKH", "customer_name": "Минстрой", "contractor_name": "СофтДев" }
}
```

## Валидация полноты документа

Перед отправкой на согласование (вызывается фронтендом):
```
POST /api/catalog/documents/:id/validate
→ 200: { is_valid: true, warnings: [] }
→ 200: { is_valid: false, errors: ["section.1.customer_name: required"], warnings: ["section.4.2: 0 functions"] }
```

## Seed Data

4 базовых шаблона (is_system: true, project_id: null):
- ТЗ (ГОСТ 34.602-2020): ~10 секций, 3 auto (4.1, 4.2, 5)
- ЧТЗ (практика): ~6 секций, 2 auto (1, 3)
- ПМИ (ГОСТ 34.603-92): ~7 секций, 2 auto (6, 7)
- НМЦК (44-ФЗ): output_format=xlsx

Файлы шаблонов: `seeds/templates/*.json`

## Переменные окружения
```env
MONGO_HOST=catalog-mongodb
MONGO_PORT=27017
MONGO_DB=catalog_db
MONGO_USER=catalog_user
MONGO_PASSWORD=<secret>
AUTH_SERVICE_URL=http://auth-service:8001
WORKFLOW_SERVICE_URL=http://workflow-service:8004
INTERNAL_API_SECRET=<secret>
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
REDIS_URL=redis://redis:6379/0        # опционально, fallback на in-memory
```

## Структура кода
```
catalog-service/
  app/
    main.py
    config.py
    models/           # Beanie Document models
    schemas/          # Pydantic request/response
    services/         # function_service, template_service, document_service
    api/              # FastAPI роуты
  seeds/
    templates/        # JSON-файлы базовых шаблонов
    seed_templates.py
  tests/
  Dockerfile
  requirements.txt
```
