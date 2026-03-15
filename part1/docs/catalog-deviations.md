# Catalog Service — отклонения от спецификации

## Что реализовано иначе

### 1. Кастомный обработчик HTTPException → `{"error": {...}}`
**Спецификация:** формат ошибок `{ "error": { "code": "...", "message": "...", "details": {} } }`.
**FastAPI по умолчанию:** оборачивает в `{ "detail": {...} }`.
**Реализовано:** добавлен `@app.exception_handler(FastAPIHTTPException)` в `main.py`, который переупаковывает `detail` → `error`. Применяется ко всем 4xx/5xx ответам.

### 2. Мягкое удаление функций через `status: "deleted"` (не физическое удаление)
**Спецификация:** функции не должны физически удаляться.
**Реализовано:** `DELETE /api/catalog/functions/:id` устанавливает `status = "deleted"`. GET-запросы фильтруют `{"status": {"$ne": "deleted"}}`. Запись остаётся в MongoDB.

### 3. document.status изменяется только извне (через Workflow Service)
**Спецификация:** Catalog управляет содержимым, Workflow — жизненным циклом.
**Реализовано:** Catalog не предоставляет эндпоинта для смены status документа. Статус меняется напрямую в MongoDB (Workflow через internal API или прямое подключение — TBD).
**Следствие:** в тестах locked-документ создаётся с `status="pending"` напрямую через Beanie.

### 4. `project_id` в ставках — строка, не UUID
**Спецификация:** project_id везде UUID.
**Реализовано:** в модели `Rates` и URL `/api/catalog/rates/:project_id` — строка. Проверка роли в `require_project_role` выполняет `str(r.project_id) == project_id` (строковое сравнение), что работает как с UUID-строкой, так и с любым форматом.

### 5. Аудит — запись в локальную MongoDB, не в Auth Service
**Спецификация:** аудит агрегируется Auth Service.
**Реализовано:** `write_audit()` пишет в коллекцию `audit_logs` в той же MongoDB (catalog_db). Auth агрегирует через `/internal/audit` в v2.

---

## Что добавлено сверх спецификации

- **`correlation_id` middleware** — `X-Request-ID` в каждом запросе и ответе (structlog).
- **`render_rule` в секциях шаблона** — `functions_grouped_by_subsystem`, `subsystems_list` — семантические инструкции для Generation Service.
- **`function_template` в секции 4.2** — шаблон рендера функции (heading, body, requirements_list) хранится в шаблоне, не в Generation Service.
- **`doc_refs` в функции** — перекрёстные ссылки на разделы ТЗ/ЧТЗ/ПМИ и строку НМЦК.
- **`test_params` в функции** — критерии приёмки, подход к тестированию, тестовые данные.
- **`dotx_file_key` в шаблоне** — путь к .dotx-файлу в MinIO (для Generation Service).

---

## Что отложено (не реализовано в MVP)

| Функция | Статус | Комментарий |
|---------|--------|-------------|
| Смена `document.status` через API | Не реализовано | Ответственность Workflow Service |
| Полнотекстовый поиск функций (`?q=`) | Фильтр в API есть | MongoDB text index не создаётся автоматически |
| Клонирование (fork) шаблона | Поле `parent_id` есть | Логика deep copy секций не реализована |
| Загрузка .dotx в MinIO | Поле `dotx_file_key` есть | MinIO-интеграция в Generation Service |
| Пагинация для functions/templates | Для documents есть | Для остальных — `to_list()` без limit |
| Kafka/event emit при изменениях | — | v2: EventEmitter → Workflow |

---

## Известные ограничения

- Mongomock-motor не поддерживает `$text` поиск — тест на `?q=` не запускался автоматически.
- `session`-скоуп `test_app` фикстуры означает, что все 24 теста делят одну MongoDB. Порядок тестов важен при проверке счётчиков (`total >= 1`, а не `== 1`).
- `check_db_connection()` в тестах заменена заглушкой — реальный ping mongomock не поддерживается стабильно.
