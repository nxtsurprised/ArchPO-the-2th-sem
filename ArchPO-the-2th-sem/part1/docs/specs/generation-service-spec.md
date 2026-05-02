# Generation Service — Спецификация

## Обзор

Stateless сервис для генерации .docx (ТЗ, ЧТЗ, ПМИ) и .xlsx (НМЦК). Получает render-bundle из Catalog, рендерит документ, сохраняет в MinIO. Асинхронная модель с job-ами.

**БД:** нет (stateless). Job-ы in-memory.  
**Порт:** 8003

## API-эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/generation/jobs` | Запуск генерации. Body: { document_id, format: "docx"\|"xlsx" } → 202: { job_id, status: "pending" } |
| GET | `/api/generation/jobs/:job_id` | Статус: pending → processing → completed / failed. { job_id, status, progress, file_url?, checksum?, error?, warnings? } |
| GET | `/api/generation/jobs/:job_id/download` | Редирект на presigned MinIO URL. Проверяет SHA-256. 302 / 404 / 409 checksum mismatch |
| GET | `/api/generation/documents/:document_id/files` | История генераций: [{ job_id, format, created_at, file_size, checksum }] |
| GET | `/internal/audit` | Аудит-записи для агрегации |

### Idempotency
Если для document_id + format уже есть job в статусе pending/processing — вернуть существующий job вместо создания нового.

## Job модель (in-memory)

```python
class Job:
    id: str                  # UUID
    document_id: str
    format: Literal["docx", "xlsx"]
    status: Literal["pending", "processing", "completed", "failed"]
    progress: int = 0        # 0-100 (обработано секций / всего секций)
    created_at: datetime
    completed_at: datetime | None
    file_key: str | None     # путь в MinIO
    checksum: str | None     # SHA-256
    error: str | None
    warnings: list[str]
    requested_by: str        # user_id из JWT
```

При перезапуске сервиса незавершённые job-ы теряются (приемлемо для MVP).

## Пайплайн генерации (6 этапов)

### Этап 1: Валидация render-bundle
```python
validate_bundle(bundle) → ValidationResult
  - missing_fields: ["section.1.customer_name"]
  - warnings: ["section.4.2: 0 functions"]
  - is_valid: true/false
```
При ошибке: job.status = "failed", job.error = список незаполненных полей.

### Этап 2: Подготовка контента (секция за секцией)
```python
for section in template.sections:
    match section.source:
        "manual"     → render_manual(section, document_data)
        "functions"  → render_functions(section, functions, subsystems)
        "subsystems" → render_subsystems(section, subsystems)
        "static"     → render_static(section)
```
Каждый renderer возвращает промежуточный формат (абзацы, заголовки, списки, таблицы) — не привязанный к python-docx.

### Этап 3: render_functions (ключевой)
```python
render_functions(section, functions, subsystems):
    grouped = group_by(functions, "subsystem_id")
    for subsystem in sorted(subsystems, key="order"):
        emit heading(H3): "4.2.{n} {subsystem.name}"
        for func in grouped[subsystem.id]:
            emit heading(H4): "{func.code} {func.name}"
            emit paragraph: func.description
            if func.requirements:
                emit numbered_list: func.requirements
            if func.constraints:
                emit paragraph: "Ограничения: {func.constraints}"
```

### Этап 4: Форматирование по ГОСТ 2.105

**Подход: .dotx шаблон.** python-docx открывает .dotx с готовыми стилями. GostFormatter маппит семантические элементы на имена стилей:

```python
STYLE_MAP = {
    "heading_1":   "Заголовок 1",
    "heading_2":   "Заголовок 2",
    "heading_3":   "Заголовок 3",
    "body_text":   "Основной текст",
    "list_bullet": "Маркированный",
    "list_number": "Нумерованный",
    "table_head":  "Шапка таблицы",
    "table_cell":  "Ячейка таблицы",
}
```

**Fallback:** если .dotx недоступен — программные стили (GostFormatter legacy).

**Правила ГОСТ 2.105-2019:**

| Параметр | Значение | python-docx |
|----------|----------|-------------|
| Бумага | A4 (210×297) | width: 11906 DXA |
| Поле левое | 30 мм | left: 1701 DXA |
| Поле правое | 15 мм | right: 850 DXA |
| Поле верхнее/нижнее | 20 мм | top/bottom: 1134 DXA |
| Шрифт | Times New Roman, 14 пт | font: TNR, size: 28 |
| Интервал | 1,5 строки | line_spacing: 360 |
| Абзацный отступ | 1,25 см | first_line: 709 DXA |
| Выравнивание | По ширине | JUSTIFIED |
| Заголовок раздела (H1) | Прописные, полужирный, по центру | bold, upper(), CENTER |
| Заголовок подраздела (H2) | С отступа, полужирный | bold, indent: 709 |
| Нумерация страниц | Внизу по центру | footer, CENTER |
| Маркированный список | Дефис «–» | bullet: "\u2013" |
| Таблицы | «Таблица N — Название» | LEFT, no indent, repeat_header_row |

### Этап 5: Сохранение
```python
buffer = docx_to_buffer(document)
checksum = sha256(buffer)
file_key = f"projects/{project_id}/docs/{document_id}/{job_id}.docx"
minio.put_object(bucket, file_key, buffer)
```

### Этап 6: Обратная связь (опционально)
```
PATCH Catalog /internal/functions/batch-update-refs
  [{ "func_id": "func-042", "doc_refs.tz_section": "4.2.1" }]
```

## НМЦК в .xlsx (openpyxl)

### Лист 1: Расчёт НМЦК
| № | Функция | Трудозатраты, ч | Ставка, ₽/ч | Коэф. сложности | Накладные | Итого, ₽ |
|---|---------|----------------|-------------|-----------------|-----------|----------|
| 1 | ФБ-01 Авторизация ЕСИА | 120 | =Справочник!B2 | =Справочник!B5 | =Справочник!B8 | =C*D*E*F |
| ... | ... | ... | ... | ... | ... | ... |
| | Итого без НДС | =SUM(C) | | | | =SUM(G) |
| | НДС (20%) | | | | | =G_total * Справочник!B9 |
| | **НМЦК** | | | | | =G_total + G_nds |

### Лист 2: Справочник ставок
Параметры из rates проекта: базовая ставка, коэффициенты, накладные, НДС, маржа.

### Лист 3: Сводка по подсистемам
| Подсистема | Кол-во функций | Стоимость |
|-----------|---------------|-----------|
| =COUNTIF(...) | =SUMIF(...) |

**Формулы, не значения.** Заказчик может менять числа — итоги пересчитываются.

## Обработка ошибок

| Категория | Этап | Действие |
|-----------|------|----------|
| Незаполненные поля | 1 (валидация) | job.status = "failed", error = список полей |
| Баг в рендерере | 2-4 | job.status = "failed", error = техническое описание, запись в лог |
| MinIO недоступен | 5 | 3 retry с экспоненциальной задержкой. После 3 — failed |

## Audit Actions
- `generation.start` — запуск (document_id, format)
- `generation.complete` — успех (file_key, checksum, duration_ms)
- `generation.failed` — ошибка (error_type, message)
- `generation.download` — скачивание (file_key)

## Холодное хранилище (archive_service)

Фоновый воркер запускается в `lifespan` и работает всё время жизни сервиса.

**Алгоритм (каждые `ARCHIVE_INTERVAL_HOURS` часов):**
1. `GET /internal/documents/archivable?days=ARCHIVE_AFTER_DAYS` → список кандидатов из catalog
2. Для каждого документа: `MinioClient.list_objects_by_prefix(f"projects/{project_id}/docs/{doc_id}/")` → берёт самый свежий файл
3. `MinioClient.copy_to_archive(key)` → копирует `documents` → `documents-archive`, удаляет из hot bucket
4. `PATCH /internal/documents/{id}/archive` → обновляет `archived=true` в MongoDB

**Graceful degradation:** если MinIO или catalog недоступны — логирует warning, следующая итерация через `ARCHIVE_INTERVAL_HOURS`.

**file_key формат:** `projects/{project_id}/docs/{document_id}/{job_id}.{ext}`  
Воркер находит файл по префиксу `projects/{project_id}/docs/{document_id}/` — независимо от `job_id`.

## Переменные окружения
```env
CATALOG_SERVICE_URL=http://catalog-service:8002
AUTH_SERVICE_URL=http://auth-service:8001
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=<key>
MINIO_SECRET_KEY=<secret>
MINIO_BUCKET=documents
MINIO_TEMPLATES_BUCKET=templates
MINIO_ARCHIVE_BUCKET=documents-archive
PRESIGNED_URL_EXPIRY=900
INTERNAL_API_SECRET=<secret>
REDIS_URL=redis://redis:6379/1        # опционально, fallback на in-memory
ARCHIVE_AFTER_DAYS=90                 # документы старше N дней → cold storage
ARCHIVE_INTERVAL_HOURS=24             # интервал запуска воркера
```

## Структура кода
```
generation-service/
  app/
    main.py
    config.py
    models/
      job.py
    services/
      job_manager.py            # in-memory хранилище job-ов
      generation_service.py     # оркестратор пайплайна
      archive_service.py        # фоновый воркер холодного хранилища
    pipeline/
      validator.py              # BundleValidator
      section_renderer.py       # диспетчер по source-типам
      renderers/
        manual_renderer.py
        function_renderer.py
        static_renderer.py
      formatters/
        gost_formatter.py       # ГОСТ 2.105 правила + STYLE_MAP
        docx_builder.py         # python-docx сборка
        xlsx_builder.py         # openpyxl сборка НМЦК
    storage/
      minio_client.py           # put_object, get_object_bytes, presigned_get_url,
                                # list_objects_by_prefix, copy_to_archive
    api/
      jobs.py
      internal.py
  tests/
    test_validator.py
    test_function_renderer.py
    test_gost_formatter.py
    test_xlsx_builder.py
  Dockerfile
  requirements.txt
```
