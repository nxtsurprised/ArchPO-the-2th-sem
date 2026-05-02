# Тест-кейсы PMI Agent Service

**Swagger UI:** http://localhost:8006/docs  
**Среда:** локальная, Docker Compose (PMI Agent + Ollama + ChromaDB)

> **Предварительное условие:** Ollama запущен и модель доступна (по умолчанию `mistral`).
> Проверить: `curl http://localhost:11434/api/tags`

---

## Подготовка среды

### Шаг 1 — Запустить стек

```bash
cd part1
docker-compose up -d pmi-agent ollama chromadb
```

### Шаг 2 — Загрузить модель в Ollama (если ещё нет)

```bash
docker exec ollama ollama pull mistral
```

### Шаг 3 — Проверить health

```bash
curl http://localhost:8006/health
```

### Справочные данные

| Параметр | Значение |
|----------|----------|
| **PMI Agent URL** | http://localhost:8006 |
| **Ollama URL** | http://localhost:11434 |
| **Тестовый function_id** | `F-AUTH-01` |
| **Тестовый project_id** | `aaaaaaaa-0000-0000-0000-000000000001` |
| **Тестовый document_id** | `pmi-doc-001` |

---

## Блок 1 — Health и метрики

### TC-PMI-01: Сервис запущен и доступен

**Эндпоинт:** `GET /health`

**Ожидаемый результат:** `200 OK`
```json
{ "status": "ok", "service": "pmi-agent", "version": "1.0.0" }
```

---

### TC-PMI-02: Метрики Prometheus доступны

**Эндпоинт:** `GET /metrics`

**Ожидаемый результат:** `200 OK`, Content-Type `text/plain`, присутствуют метрики:
- `pmi_runs_total`
- `pmi_draft_total`
- `pmi_fallback_total`
- `pmi_draft_duration_seconds`

```bash
curl http://localhost:8006/metrics | grep pmi_
```

---

## Блок 2 — Черновой режим (draft-function)

> Этот режим не запускает браузер. Planner генерирует тест-план, Writer формирует методику.

### TC-PMI-03: Составить черновик методики для функции

**Эндпоинт:** `POST /api/v1/pmi/draft-function`

**Тело запроса:**
```json
{
  "document_id": "pmi-doc-001",
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "function_id": "F-AUTH-01",
  "function_name": "Аутентификация пользователя",
  "function_description": "Вход в систему по логину и паролю, выдача JWT-токена",
  "acceptance_criteria": [
    "Успешный вход при верных credentials",
    "Ошибка 401 при неверном пароле",
    "Ошибка 401 для несуществующего пользователя"
  ]
}
```

**Ожидаемый результат:** `202 Accepted`
```json
{
  "task_id": "<uuid>",
  "status": "pending",
  "message": "Составление ПМИ для функции F-AUTH-01 запущено"
}
```

**Сохранить:** `task_id`.

---

### TC-PMI-04: Опросить статус задачи draft — running

**Эндпоинт:** `GET /api/v1/pmi/function-tasks/<task_id>`

*(сразу после TC-PMI-03)*

**Ожидаемый результат:** `200 OK`
```json
{ "status": "running", "function_id": "F-AUTH-01", ... }
```

---

### TC-PMI-05: Дождаться завершения draft-задачи

**Эндпоинт:** `GET /api/v1/pmi/function-tasks/<task_id>`

*(подождать 15–60 секунд — зависит от скорости Ollama)*

**Ожидаемый результат:** `200 OK`
```json
{
  "status": "done",
  "function_id": "F-AUTH-01",
  "pmi_section": {
    "function_id": "F-AUTH-01",
    "function_name": "Аутентификация пользователя",
    "test_objective": "...",
    "method": "Проверка",
    "gost_ref": "ГОСТ 34.603-92",
    "verdict": "испытание не проводилось",
    "steps_total": <N>,
    "steps_passed": null,
    "_draft": true
  },
  "duration_sec": <число>
}
```

**Проверить:**
- `status = "done"`
- `pmi_section._draft = true`
- `pmi_section.steps_total > 0`
- `pmi_section.verdict = "испытание не проводилось"`

---

### TC-PMI-06: Несуществующая function-task → 404

**Эндпоинт:** `GET /api/v1/pmi/function-tasks/00000000-0000-0000-0000-000000000000`

**Ожидаемый результат:** `404 Not Found`
```json
{ "detail": "Задача не найдена" }
```

---

### TC-PMI-07: Черновик с пустыми acceptance_criteria

**Тело запроса:** то же, что TC-PMI-03, но `"acceptance_criteria": []`

**Ожидаемый результат:** `202 Accepted`, задача завершается со статусом `done`.
Planner строит тест-план только на основе `function_description`.

---

### TC-PMI-08: Черновик с tz_context (контекст технического задания)

Если Catalog Service запущен, pmi-agent получает ТЗ-контекст автоматически.
В изолированном тесте проверяем fallback — без ТЗ-контекста сервис не падает.

**Проверить:** `status = "done"` даже если Catalog недоступен
*(ошибка получения tz_context логируется как warning, не блокирует)*

---

## Блок 3 — Полный пайплайн (run)

> Требует: браузер Playwright + реальный целевой URL. В dev-среде — можно использовать `http://nginx` (фронтенд системы).

### TC-PMI-09: Запустить полный PMI-пайплайн

**Эндпоинт:** `POST /api/v1/pmi/run`

**Тело запроса:**
```json
{
  "function_id": "F-AUTH-01",
  "function_name": "Аутентификация пользователя",
  "function_description": "Вход в систему по логину и паролю, выдача JWT-токена",
  "acceptance_criteria": [
    "Успешный вход при верных credentials",
    "Ошибка 401 при неверном пароле"
  ],
  "project_id": "aaaaaaaa-0000-0000-0000-000000000001",
  "target_url": "http://nginx"
}
```

**Ожидаемый результат:** `202 Accepted`
```json
{
  "task_id": "<uuid>",
  "status": "pending",
  "message": "PMI-пайплайн запущен для функции F-AUTH-01"
}
```

**Сохранить:** `task_id`.

---

### TC-PMI-10: Опросить статус полного пайплайна — завершён

**Эндпоинт:** `GET /api/v1/pmi/tasks/<task_id>`

*(подождать 1–5 минут)*

**Ожидаемый результат:** `200 OK`
```json
{
  "task_id": "<uuid>",
  "status": "done",
  "function_id": "F-AUTH-01",
  "verdict": "соответствует" | "не соответствует",
  "steps_total": <N>,
  "steps_passed": <N>,
  "pmi_section": {
    "verdict": "...",
    "observations": "...",
    "defects": [...],
    "recommendation": "...",
    "_draft": false  ← отсутствует или false
  }
}
```

**Проверить:**
- `status = "done"`
- `verdict` — одно из: `"соответствует"`, `"не соответствует"`
- `steps_total >= 1`
- `pmi_section.observations` — непустая строка

---

### TC-PMI-11: Несуществующий task → 404

**Эндпоинт:** `GET /api/v1/pmi/tasks/00000000-0000-0000-0000-000000000000`

**Ожидаемый результат:** `404 Not Found`
```json
{ "detail": "Задача не найдена" }
```

---

### TC-PMI-12: Список всех задач (отладка)

**Эндпоинт:** `GET /api/v1/pmi/tasks`

**Ожидаемый результат:** `200 OK`, массив с созданными задачами из TC-PMI-09+.
```json
[
  {
    "task_id": "<uuid>",
    "function_id": "F-AUTH-01",
    "status": "done",
    "verdict": "соответствует"
  }
]
```

---

## Блок 4 — Knowledge Base

### TC-PMI-13: Перезагрузить knowledge base

**Эндпоинт:** `POST /api/v1/knowledge/reload`

**Ожидаемый результат:** `200 OK`
```json
{ "status": "ok", "chunks_loaded": <N> }
```

> `chunks_loaded > 0` — значит ГОСТ 34.603 успешно проиндексирован в ChromaDB.

---

### TC-PMI-14: Fallback при недоступном LLM

Остановить Ollama: `docker-compose stop ollama`

Запустить черновик (TC-PMI-03).

**Ожидаемый результат:** задача завершается со статусом `done`, в `pmi_section` присутствует поле `_fallback: true` или тест-план заполнен минимальными данными.

Метрика `pmi_fallback_total` увеличивается на 1:
```bash
curl http://localhost:8006/metrics | grep pmi_fallback_total
```

Запустить Ollama обратно: `docker-compose start ollama`

---

## Блок 5 — Webhook для Alertmanager

### TC-PMI-15: Alertmanager webhook принимает алерты

**Эндпоинт:** `POST /api/v1/alerts`

**Тело запроса:**
```json
{
  "alerts": [
    {
      "labels": { "alertname": "HighLatency", "severity": "warning" },
      "annotations": {
        "summary": "PMI pipeline too slow",
        "description": "Duration > 5 min"
      },
      "status": "firing"
    }
  ]
}
```

**Ожидаемый результат:** `200 OK`
```json
{ "received": 1 }
```

Алерт появляется в структурированных логах:
```bash
docker logs pmi-agent 2>&1 | grep alert_received
```

---

## Сводная таблица

| №           | Эндпоинт                                        | Что проверяет                            | Ожидаемый статус |
|-------------|-------------------------------------------------|------------------------------------------|-----------------|
| TC-PMI-01   | GET /health                                     | Сервис запущен                           | 200             |
| TC-PMI-02   | GET /metrics                                    | Prometheus-метрики экспортируются        | 200             |
| TC-PMI-03   | POST /api/v1/pmi/draft-function                 | Запуск черновика методики                | 202             |
| TC-PMI-04   | GET /api/v1/pmi/function-tasks/:id (running)    | Статус running пока LLM работает         | 200             |
| TC-PMI-05   | GET /api/v1/pmi/function-tasks/:id (done)       | Черновик готов, _draft=true              | 200             |
| TC-PMI-06   | GET /api/v1/pmi/function-tasks/nonexistent      | 404 для несуществующей задачи            | 404             |
| TC-PMI-07   | POST draft-function (пустые criteria)           | Работает без acceptance_criteria         | 202             |
| TC-PMI-08   | POST draft-function (без Catalog)               | Fallback при недоступном tz_context      | 202             |
| TC-PMI-09   | POST /api/v1/pmi/run                            | Запуск полного пайплайна с Playwright    | 202             |
| TC-PMI-10   | GET /api/v1/pmi/tasks/:id (done)                | Вердикт, шаги, pmi_section               | 200             |
| TC-PMI-11   | GET /api/v1/pmi/tasks/nonexistent               | 404 для несуществующего task             | 404             |
| TC-PMI-12   | GET /api/v1/pmi/tasks                           | Список всех задач                        | 200             |
| TC-PMI-13   | POST /api/v1/knowledge/reload                   | Перезагрузка ChromaDB                    | 200             |
| TC-PMI-14   | POST draft-function (Ollama выключен)           | Fallback при недоступном LLM             | 202+done        |
| TC-PMI-15   | POST /api/v1/alerts                             | Webhook Alertmanager принят              | 200             |
