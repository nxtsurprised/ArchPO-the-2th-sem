# Тест-кейсы Generation Service

**Swagger UI:** http://localhost:8003/docs
**Среда:** локальная, Docker Compose (Generation + Catalog + MinIO + Auth)

> **Предварительное условие:** пройти TC-01 – TC-37 из `test-cases-catalog.md`
> и сохранить `document_id` из TC-27 (создание документа ТЗ).
> Именно этот документ будет использоваться для генерации.

---

## Подготовка среды

### Шаг 1 — Запустить полный стек

```bash
cd part1
docker-compose up -d auth-service catalog-service generation-service minio nginx
```

Подождать, пока все сервисы перейдут в `healthy`:

```bash
docker-compose ps
```

---

### Шаг 2 — Получить JWT-токен

Токен выпускается Auth Service. В dev-режиме — скриптом:

```bash
# PM (заказчик) — максимальные права
docker exec catalog-service python3 scripts/make_dev_token.py pm customer
```

Вставить токен в Swagger UI на http://localhost:8003/docs → кнопка **Authorize**.

---

### Справочные данные

| Параметр           | Значение                                           |
|--------------------|----------------------------------------------------|
| **DOCUMENT_ID**    | `<id из TC-27 catalog>` *(сохранить)*             |
| **PROJECT_ID**     | `aaaaaaaa-0000-0000-0000-000000000001`             |
| **MinIO Console**  | http://localhost:9001 (minioadmin / minioadmin)   |
| **Bucket docs**    | `documents`                                        |
| **Bucket templates** | `templates`                                      |
| **INTERNAL_API_SECRET** | `internal_secret`                           |

---

## Блок 1 — Health

### TC-GEN-01: Сервис запущен и доступен

**Эндпоинт:** `GET /health`
*(авторизация не нужна)*

**Ожидаемый результат:** `200 OK`
```json
{ "status": "ok", "db": "connected", "version": "1.0.0" }
```

> Поле `db` у Generation Service всегда `"connected"` — сервис stateless, нет своей БД.

---

## Блок 2 — Запуск генерации (POST /api/generation/jobs)

> Для всех тестов блока: авторизоваться токеном **PM**.

### TC-GEN-02: Запустить генерацию .docx

**Эндпоинт:** `POST /api/generation/jobs`

**Тело запроса:**
```json
{
  "document_id": "<DOCUMENT_ID>",
  "format": "docx"
}
```

**Ожидаемый результат:** `202 Accepted`
```json
{ "job_id": "<uuid>", "status": "pending" }
```

**Сохранить:** `job_id` — понадобится в TC-GEN-05–08.

---

### TC-GEN-03: Запустить генерацию .xlsx (НМЦК)

**Эндпоинт:** `POST /api/generation/jobs`

**Тело запроса:**
```json
{
  "document_id": "<DOCUMENT_ID>",
  "format": "xlsx"
}
```

**Ожидаемый результат:** `202 Accepted`
```json
{ "job_id": "<uuid>", "status": "pending" }
```

**Сохранить:** `job_id` для xlsx — понадобится в TC-GEN-09.

---

### TC-GEN-04: Idempotency — повторный запрос возвращает тот же job

**Эндпоинт:** `POST /api/generation/jobs` *(тот же запрос, что TC-GEN-02)*

**Тело запроса:**
```json
{
  "document_id": "<DOCUMENT_ID>",
  "format": "docx"
}
```

**Ожидаемый результат:** `202 Accepted`, **`job_id` совпадает** с TC-GEN-02.

> Если job уже в статусе `completed` — создаётся новый. Idempotency работает только для `pending` / `processing`.

---

### TC-GEN-05: Неверный format → 422

**Эндпоинт:** `POST /api/generation/jobs`

**Тело запроса:**
```json
{
  "document_id": "<DOCUMENT_ID>",
  "format": "pdf"
}
```

**Ожидаемый результат:** `422 Unprocessable Entity`
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed" } }
```

---

### TC-GEN-06: Без авторизации → 401

**Эндпоинт:** `POST /api/generation/jobs` *(без заголовка Authorization)*

**Тело запроса:**
```json
{ "document_id": "<DOCUMENT_ID>", "format": "docx" }
```

**Ожидаемый результат:** `401 Unauthorized`
```json
{ "error": { "code": "UNAUTHORIZED", "message": "Missing or invalid Authorization header" } }
```

---

## Блок 3 — Статус job-а (GET /api/generation/jobs/:job_id)

### TC-GEN-07: Опросить статус — job в процессе

**Эндпоинт:** `GET /api/generation/jobs/<job_id>` *(job_id из TC-GEN-02, сразу после создания)*

**Ожидаемый результат:** `200 OK`
```json
{
  "job_id": "<uuid>",
  "document_id": "<DOCUMENT_ID>",
  "format": "docx",
  "status": "processing",
  "progress": 40,
  "created_at": "2026-03-15T10:00:00+00:00",
  "completed_at": null,
  "checksum": null,
  "error": null,
  "warnings": []
}
```

> `status` может быть уже `completed` если генерация прошла быстро — это нормально.

---

### TC-GEN-08: Опросить статус — job завершён

**Эндпоинт:** `GET /api/generation/jobs/<job_id>`
*(подождать 5–10 секунд после TC-GEN-02)*

**Ожидаемый результат:** `200 OK`
```json
{
  "job_id": "<uuid>",
  "status": "completed",
  "progress": 100,
  "completed_at": "2026-03-15T10:00:08+00:00",
  "checksum": "<sha256-hex>",
  "error": null,
  "warnings": []
}
```

**Проверить:**
- `status = "completed"`
- `progress = 100`
- `checksum` — непустая строка (SHA-256, 64 символа hex)
- `completed_at` — не null

---

### TC-GEN-09: Несуществующий job → 404

**Эндпоинт:** `GET /api/generation/jobs/00000000-0000-0000-0000-000000000000`

**Ожидаемый результат:** `404 Not Found`
```json
{ "error": { "code": "JOB_NOT_FOUND", "message": "Job 00000000-0000-0000-0000-000000000000 not found" } }
```

---

## Блок 4 — Скачивание (GET /api/generation/jobs/:job_id/download)

> **Предварительное условие:** дождаться `status = "completed"` (TC-GEN-08).

### TC-GEN-10: Скачать готовый .docx файл

**Эндпоинт:** `GET /api/generation/jobs/<job_id>/download`

**Ожидаемый результат:** `302 Found`
Заголовок `Location` содержит presigned MinIO URL вида:
```
http://minio:9000/documents/projects/aaaaaaaa-.../docs/<doc_id>/<job_id>.docx?X-Amz-...
```

**Как проверить через curl:**
```bash
curl -L -o result.docx \
  -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8003/api/generation/jobs/<job_id>/download"
```

**Проверить результат:**
```bash
file result.docx
# → result.docx: Microsoft Word 2007+

# Проверить размер (должен быть >5 KB)
ls -lh result.docx

# Открыть в LibreOffice
libreoffice --writer result.docx
```

**В документе должны быть:**
- Раздел «1 Общие сведения» с полями `system_name`, `customer_name`
- Раздел «4.2 Требования к функциям» с заголовком функции ФБ-01
- Требования в виде нумерованного списка
- Раздел «5 Состав и содержание работ»

---

### TC-GEN-11: Скачать готовый .xlsx (НМЦК)

*(job_id из TC-GEN-03, дождаться completed)*

**Эндпоинт:** `GET /api/generation/jobs/<job_id_xlsx>/download`

```bash
curl -L -o nmck.xlsx \
  -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8003/api/generation/jobs/<job_id_xlsx>/download"
```

**Открыть в LibreOffice Calc или Excel. Проверить:**

| Лист | Ожидаемое содержимое |
|------|-----------------------|
| Расчёт НМЦК | Строка с ФБ-01, трудозатраты 40 ч, формула в колонке Итого |
| Справочник | Базовая ставка 3500, НДС 0.20 |
| Сводка | Строка «ПБ — Подсистема информационной безопасности», кол-во функций |

**Ключевые проверки в таблице НМЦК:**
- Ячейка D2 содержит формулу `=Справочник!$B$2` (не число 3500)
- Ячейка E2 содержит формулу `=Справочник!$B$4` (коэф. medium)
- Ячейка G2 содержит формулу `=C2*D2*E2*F2`
- Изменение B2 в Справочнике пересчитывает итоги

---

### TC-GEN-12: Скачать незавершённый job → 409

**Эндпоинт:** `GET /api/generation/jobs/<job_id>/download`
*(сразу после TC-GEN-02, пока статус `pending`)*

**Ожидаемый результат:** `409 Conflict`
```json
{ "error": { "code": "JOB_NOT_COMPLETED", "message": "Job status: pending" } }
```

---

### TC-GEN-13: Скачать несуществующий job → 404

**Эндпоинт:** `GET /api/generation/jobs/nonexistent-id/download`

**Ожидаемый результат:** `404 Not Found`
```json
{ "error": { "code": "JOB_NOT_FOUND", "message": "Job nonexistent-id not found" } }
```

---

### TC-GEN-14: Проверка контрольной суммы в MinIO

*(После успешного TC-GEN-10)*

```bash
# Получить checksum из статуса job-а
JOB_CHECKSUM=$(curl -s -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8003/api/generation/jobs/<job_id>" | python3 -m json.tool | grep checksum | awk -F'"' '{print $4}')

# Вычислить SHA-256 скачанного файла
FILE_CHECKSUM=$(sha256sum result.docx | awk '{print $1}')

echo "Job checksum:  $JOB_CHECKSUM"
echo "File checksum: $FILE_CHECKSUM"

# Должны совпасть
[ "$JOB_CHECKSUM" = "$FILE_CHECKSUM" ] && echo "OK" || echo "MISMATCH"
```

**Ожидаемый результат:** `OK`

---

## Блок 5 — История генераций

### TC-GEN-15: Список файлов документа

*(После TC-GEN-02 и TC-GEN-03, оба в статусе completed)*

**Эндпоинт:** `GET /api/generation/documents/<DOCUMENT_ID>/files`

**Ожидаемый результат:** `200 OK`
```json
[
  {
    "job_id": "<uuid-docx>",
    "format": "docx",
    "created_at": "2026-03-15T10:00:00+00:00",
    "file_size": 12345,
    "checksum": "<sha256>"
  },
  {
    "job_id": "<uuid-xlsx>",
    "format": "xlsx",
    "created_at": "2026-03-15T10:00:05+00:00",
    "file_size": 8192,
    "checksum": "<sha256>"
  }
]
```

**Проверить:** два элемента — docx и xlsx, оба с ненулевым `file_size` и `checksum`.

---

### TC-GEN-16: Список файлов для несуществующего документа — пустой массив

**Эндпоинт:** `GET /api/generation/documents/no-such-doc/files`

**Ожидаемый результат:** `200 OK`
```json
[]
```

---

## Блок 6 — Граничные случаи

### TC-GEN-17: Генерация документа без функций

Создать в Catalog документ без привязанных функций (без `function_ids`), затем:

**Эндпоинт:** `POST /api/generation/jobs`

**Тело:**
```json
{ "document_id": "<doc_без_функций>", "format": "docx" }
```

Дождаться завершения. Статус проверить:

**Ожидаемый результат:** `status: "completed"`, в `warnings` содержит предупреждение
```json
{ "warnings": ["section.4.2: 0 functions"] }
```

Документ при этом генерируется, но раздел 4.2 будет пустым.

---

### TC-GEN-18: Генерация документа с незаполненными обязательными полями

Создать в Catalog документ без `system_name` и `customer_name` в `data.sections.1`.

**Эндпоинт:** `POST /api/generation/jobs`

```json
{ "document_id": "<doc_незаполненный>", "format": "docx" }
```

Дождаться завершения. Статус:

**Ожидаемый результат:** `status: "failed"`
```json
{
  "status": "failed",
  "error": "Missing required fields: section.1.system_name, section.1.customer_name"
}
```

---

### TC-GEN-19: Повторный запуск после failed — создаёт новый job

*(после TC-GEN-18)*

**Эндпоинт:** `POST /api/generation/jobs`

```json
{ "document_id": "<doc_незаполненный>", "format": "docx" }
```

**Ожидаемый результат:** `202 Accepted`, **новый** `job_id` (отличается от TC-GEN-18).

> `failed` job не блокирует новую попытку — idempotency применяется только к `pending/processing`.

---

### TC-GEN-20: Два разных формата — разные job-ы

Убедиться, что для одного `document_id` можно одновременно иметь job на `docx` и отдельный на `xlsx`:

**Запрос 1:** `POST /api/generation/jobs` `{ format: "docx" }`
**Запрос 2:** `POST /api/generation/jobs` `{ format: "xlsx" }`

**Ожидаемый результат:** два разных `job_id`.

---

## Блок 7 — Internal API

> Запросы через `curl` — эти эндпоинты блокируются nginx (`/internal/*`).
> Обращаться напрямую к контейнеру: порт 8003 изнутри Docker-сети.

### TC-GEN-21: /internal/audit — без секрета → 403

```bash
curl http://localhost:8003/internal/audit
```

**Ожидаемый результат:** `403 Forbidden`
```json
{ "error": { "code": "FORBIDDEN", "message": "Invalid internal secret" } }
```

---

### TC-GEN-22: /internal/audit — с секретом

```bash
curl http://localhost:8003/internal/audit \
  -H "X-Internal-Secret: internal_secret"
```

**Ожидаемый результат:** `200 OK`
```json
{
  "items": [
    { "action": "generation.start",    "timestamp": "...", "document_id": "...", "format": "docx" },
    { "action": "generation.complete", "timestamp": "...", "file_key": "...", "duration_ms": 3200 }
  ],
  "total": 2
}
```

**Проверить** наличие хотя бы одной записи `generation.complete` после TC-GEN-02.

---

## Блок 8 — Проверка файлов в MinIO

*(После TC-GEN-10 и TC-GEN-11)*

### TC-GEN-23: Файл существует в MinIO

**Открыть:** http://localhost:9001 (minioadmin / minioadmin)
Перейти: **Buckets → documents → projects/aaaaaaaa-.../docs/\<DOCUMENT_ID\>/**

**Проверить:**
- Есть файл `<job_id>.docx`
- Есть файл `<job_id>.xlsx`

Или через `mc` CLI:

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
mc ls local/documents/projects/aaaaaaaa-0000-0000-0000-000000000001/docs/<DOCUMENT_ID>/
```

---

### TC-GEN-24: Presigned URL — файл доступен по прямой ссылке

Взять URL из заголовка `Location` при TC-GEN-10 (без follow redirect):

```bash
curl -v -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8003/api/generation/jobs/<job_id>/download" 2>&1 | grep Location
```

Скачать файл по presigned URL без Authorization:

```bash
curl -o via_presigned.docx "<presigned_url_из_Location>"
```

**Ожидаемый результат:** файл скачивается (200 OK), не требует авторизации.
**Размер** совпадает с `file_size` из TC-GEN-15.

---

## Блок 9 — Холодное хранилище (архивирование)

> Архивный воркер переносит файлы старше `ARCHIVE_AFTER_DAYS` (по умолчанию 90 дней)
> из bucket `documents` в bucket `archive`. Тесты имитируют давние файлы через прямую запись в MinIO.

### TC-GEN-25: Архивный воркер запускается без ошибок

```bash
docker exec generation-service python3 -m app.workers.archive_worker --dry-run
```

**Ожидаемый результат:** вывод без traceback, строка вида:
```
[dry-run] Would archive N files older than 90 days
```

---

### TC-GEN-26: Файл старше порога переносится в archive bucket

1. Создать тестовый файл в MinIO с датой `LastModified` > 90 дней назад:

```bash
# Загрузить файл с прошедшей датой через mc
mc alias set local http://localhost:9000 minioadmin minioadmin
mc cp /dev/urandom --limit-size=1KB local/documents/projects/test-project/docs/old-doc/old-job.docx

# Вручную установить дату — MinIO не позволяет изменить LastModified напрямую,
# поэтому используем специальный тест-хелпер:
docker exec generation-service python3 tests/helpers/create_old_file.py \
  --bucket documents \
  --key "projects/test-project/docs/old-doc/old-job.docx" \
  --days-old 91
```

2. Запустить архивный воркер:

```bash
docker exec generation-service python3 -m app.workers.archive_worker
```

3. Проверить перенос:

```bash
# Файла нет в основном bucket
mc ls local/documents/projects/test-project/docs/old-doc/ | grep old-job.docx
# → пусто

# Файл появился в archive bucket
mc ls local/archive/projects/test-project/docs/old-doc/ | grep old-job.docx
# → присутствует
```

**Ожидаемый результат:** файл перемещён, в исходном пути отсутствует.

---

### TC-GEN-27: Свежий файл не архивируется

Выполнить шаги TC-GEN-25 для файла с `days-old=10`.

**Ожидаемый результат:** файл остаётся в `documents` bucket, воркер его не трогает.

---

### TC-GEN-28: Скачивание заархивированного файла → 410 Gone

*(После TC-GEN-26)*

**Эндпоинт:** `GET /api/generation/jobs/<job_id>/download`

*(job_id соответствует заархивированному файлу)*

**Ожидаемый результат:** `410 Gone`
```json
{
  "error": {
    "code": "FILE_ARCHIVED",
    "message": "File has been moved to cold storage. Contact administrator to restore."
  }
}
```

---

## Сводная таблица

| №           | Эндпоинт                                                    | Что проверяет                                       | Ожидаемый статус |
|-------------|-------------------------------------------------------------|-----------------------------------------------------|-----------------|
| TC-GEN-01   | GET /health                                                 | Сервис запущен                                      | 200             |
| TC-GEN-02   | POST /api/generation/jobs (docx)                            | Запуск генерации .docx                              | 202             |
| TC-GEN-03   | POST /api/generation/jobs (xlsx)                            | Запуск генерации НМЦК .xlsx                         | 202             |
| TC-GEN-04   | POST /api/generation/jobs (повтор)                          | Idempotency: тот же job_id                          | 202             |
| TC-GEN-05   | POST /api/generation/jobs (format=pdf)                      | Неверный формат                                     | 422             |
| TC-GEN-06   | POST /api/generation/jobs (без токена)                      | Защита JWT                                          | 401             |
| TC-GEN-07   | GET /api/generation/jobs/:id (в процессе)                   | Статус processing + progress                        | 200             |
| TC-GEN-08   | GET /api/generation/jobs/:id (завершён)                     | Статус completed + checksum                         | 200             |
| TC-GEN-09   | GET /api/generation/jobs/nonexistent                        | Job не найден                                       | 404             |
| TC-GEN-10   | GET /api/generation/jobs/:id/download (docx)                | **Скачивание .docx**, 302 на presigned URL          | 302             |
| TC-GEN-11   | GET /api/generation/jobs/:id/download (xlsx)                | **Скачивание .xlsx**, формулы в ячейках             | 302             |
| TC-GEN-12   | GET /api/generation/jobs/:id/download (pending)             | Скачивание незавершённого job-а                     | 409             |
| TC-GEN-13   | GET /api/generation/jobs/nonexistent/download               | Job не найден                                       | 404             |
| TC-GEN-14   | Сверка SHA-256 через curl                                   | Целостность файла                                   | —               |
| TC-GEN-15   | GET /api/generation/documents/:id/files                     | История генераций: 2 файла (docx + xlsx)            | 200             |
| TC-GEN-16   | GET /api/generation/documents/no-such/files                 | Пустая история                                      | 200             |
| TC-GEN-17   | Генерация без функций                                       | warnings вместо ошибки                              | completed       |
| TC-GEN-18   | Генерация без обязательных полей                            | failed с описанием пропущенных полей                | failed          |
| TC-GEN-19   | Повтор после failed                                         | Новый job (не idempotency)                          | 202             |
| TC-GEN-20   | docx + xlsx одновременно                                    | Разные job-ы для разных форматов                    | 202 × 2         |
| TC-GEN-21   | GET /internal/audit (без секрета)                           | Защита internal API                                 | 403             |
| TC-GEN-22   | GET /internal/audit (с секретом)                            | Аудит-записи generation.*                           | 200             |
| TC-GEN-23   | MinIO Console / mc ls                                       | Файлы существуют в bucket                           | —               |
| TC-GEN-24   | Presigned URL без авторизации                               | Прямое скачивание по presigned URL                  | 200             |
| TC-GEN-25   | archive_worker --dry-run                                    | Воркер запускается без ошибок                       | —               |
| TC-GEN-26   | archive_worker (файл старше 90 дней)                        | Файл перенесён в cold storage                       | —               |
| TC-GEN-27   | archive_worker (файл 10 дней)                               | Свежий файл не архивируется                         | —               |
| TC-GEN-28   | GET /api/generation/jobs/:id/download (archived)            | 410 Gone для заархивированного файла                | 410             |

---

## Что нужно для запуска тестов прямо сейчас

### Вариант A — Юнит-тесты (без docker-compose)

```bash
cd part1/generation-service
pip install -r requirements.txt
pip install -e ../shared

pytest tests/test_validator.py tests/test_function_renderer.py -v
# ↑ работает без MinIO и без Catalog (чистая Python-логика)

pytest tests/test_gost_formatter.py tests/test_xlsx_builder.py -v
# ↑ требует python-docx и openpyxl (уже в requirements.txt)

pytest tests/test_api.py -v
# ↑ Catalog и MinIO замокированы; JWT — тестовыми ключами
```

### Вариант B — Полный E2E (скачать реальный файл)

1. Запустить `docker-compose up`
2. Пройти TC-01–TC-37 из `test-cases-catalog.md` (создать документ с функциями)
3. Выполнить TC-GEN-02 → TC-GEN-08 → TC-GEN-10
4. Открыть скачанный `result.docx` в LibreOffice / Word
