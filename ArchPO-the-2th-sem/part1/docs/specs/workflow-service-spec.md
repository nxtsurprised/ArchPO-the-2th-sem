# Workflow Service — Спецификация

## Обзор

Жизненный цикл согласования документов. Многораундовая логика с участием обеих сторон контракта. Стейт-машина: draft → pending → approved / rejected / revision. PostgreSQL.

**БД:** PostgreSQL 16  
**ORM:** SQLAlchemy 2.0 + Alembic  
**Порт:** 8004

## Модель данных (4 таблицы + audit_log)

### approval_requests
```sql
id                UUID PK DEFAULT gen_random_uuid()
document_id       VARCHAR(100) NOT NULL       -- ID документа в Catalog
project_id        UUID NOT NULL
type              VARCHAR(20) NOT NULL         -- tz_final | nmck_final | review
status            VARCHAR(20) DEFAULT 'pending' -- pending | approved | rejected | revision
initiated_by      UUID NOT NULL                -- user_id инициатора
initiated_by_side VARCHAR(20) NOT NULL         -- customer | contractor
current_round     INT DEFAULT 1
is_locked         BOOLEAN DEFAULT true         -- блокирует редактирование в Catalog
deadline          TIMESTAMP                    -- nullable, для v2 (SLA)
created_at        TIMESTAMP DEFAULT now()
updated_at        TIMESTAMP DEFAULT now()

-- Только один активный non-review запрос на документ
UNIQUE (document_id) WHERE status = 'pending' AND type != 'review'
```

### approval_rounds
```sql
id              UUID PK DEFAULT gen_random_uuid()
request_id      UUID FK → approval_requests NOT NULL
round_number    INT NOT NULL
status          VARCHAR(20) DEFAULT 'active'   -- active | completed | cancelled
final_decision  VARCHAR(20)                    -- approved | rejected | revision | null
started_at      TIMESTAMP DEFAULT now()
completed_at    TIMESTAMP
```

### approval_decisions
```sql
id              UUID PK DEFAULT gen_random_uuid()
round_id        UUID FK → approval_rounds NOT NULL
user_id         UUID NOT NULL
user_role       VARCHAR(20) NOT NULL            -- pm | analyst
user_side       VARCHAR(20) NOT NULL            -- customer | contractor
decision_type   VARCHAR(20) NOT NULL            -- approve | reject | revision | review
comment         TEXT
decided_at      TIMESTAMP DEFAULT now()

UNIQUE (round_id, user_id)  -- один пользователь = одно решение в раунде
```

### approval_comments
```sql
id              UUID PK DEFAULT gen_random_uuid()
request_id      UUID FK → approval_requests NOT NULL
user_id         UUID NOT NULL
text            TEXT NOT NULL
target_section  VARCHAR(20)                     -- к какому разделу (необязательно)
created_at      TIMESTAMP DEFAULT now()
```

### audit_log
Та же структура, что в Auth. service = "workflow".

## Типы согласований

### tz_final — ТЗ / ЧТЗ / ПМИ
- **Финальное решение:** РП заказчика **И** РП подрядчика — оба должны одобрить
- **Рецензенты:** аналитики обеих сторон (decision_type: review, не блокирует)
- **Блокировка:** is_locked = true на всё время раунда
- **Permission:** approval.decide_tz (pm), approval.review (analyst)

### nmck_final — НМЦК (стоимость)
- **Финальное решение:** РП заказчика **И** РП подрядчика
- **Рецензенты:** не предусмотрены (стоимость — только между РП)
- **Permission:** approval.decide_nmck (только pm)
- **Особенность:** при revision также блокирует изменение ставок в Catalog

### review — внутренняя рецензия
- **Финальное решение:** нет. Не меняет статус документа
- **Блокировка:** is_locked = false
- **Permission:** approval.review

## Стейт-машина

```
draft ──[отправить]──► pending ──[одобрить (оба РП)]──► approved
                           │
                           ├──[отклонить (любой РП)]──► rejected
                           │
                           └──[доработать (любой РП)]──► revision
                                                           │
                                                           └──[повторная отправка]──► pending (новый раунд)
```

## Логика evaluate_round

```python
def evaluate_round(round, approval_type):
    final_decisions = [d for d in round.decisions if d.decision_type != "review"]
    
    if approval_type in ("tz_final", "nmck_final"):
        required_sides = {"customer", "contractor"}
    else:
        return None  # review не завершает раунд
    
    decided_sides = {d.user_side for d in final_decisions}
    if decided_sides != required_sides:
        return None  # ждём остальных
    
    # Приоритет: reject > revision > approve
    if any(d.decision_type == "reject" for d in final_decisions):
        return "rejected"
    if any(d.decision_type == "revision" for d in final_decisions):
        return "revision"
    return "approved"
```

### Все комбинации (tz_final / nmck_final)

| РП заказчика | РП подрядчика | Итог раунда |
|-------------|--------------|-------------|
| approve | approve | **approved** |
| approve | revision | **revision** |
| approve | reject | **rejected** |
| revision | approve | **revision** |
| revision | revision | **revision** |
| reject | approve | **rejected** |
| reject | reject | **rejected** |
| approve | (ждём) | pending |
| (ждём) | revision | pending — раунд не закрыт |

## API-эндпоинты

### Согласования
| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/workflow/approvals` | Отправка на согласование. Body: { document_id, project_id, type } → 201: { approval_id } |
| GET | `/api/workflow/approvals/:id` | Детали: статус, инициатор, текущий раунд, рецензенты, решения |
| POST | `/api/workflow/approvals/:id/decide` | Решение. Body: { decision: "approve"\|"reject"\|"revision"\|"review", comment? } → 200 |
| POST | `/api/workflow/approvals/:id/revoke` | Отзыв решения (пока раунд не завершён) → 200 / 409 round completed |
| POST | `/api/workflow/approvals/:id/cancel` | Отмена (admin + pm). Раунд → cancelled, документ разблокирован |
| GET | `/api/workflow/approvals?project_id=&status=&my=true` | Список с фильтрами |
| GET | `/api/workflow/approvals/:id/history` | Все раунды: [{ round_number, decisions, final_status }] |

### Дашборд
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/workflow/dashboard?project_id=` | Сводка: { pending: N, approved: N, rejected: N, revision: N } |
| GET | `/api/workflow/my-tasks` | Мои ожидающие: документы, где я рецензент и ещё не высказался |

### Internal API
| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/internal/documents/:document_id/status` | { status, locked: bool } — Catalog проверяет перед PUT |
| GET | `/internal/audit` | Аудит-записи для агрегации |

## Edge Cases

1. **Документ изменили после отправки:** Невозможно — is_locked=true, Catalog проверяет /internal/status
2. **РП хочет отозвать решение:** Допускается, пока раунд не завершён. POST /revoke
3. **Два активных tz_final на один документ:** Невозможно — UNIQUE constraint
4. **tz_final и review одновременно:** Допускается — review не блокирует
5. **РП деактивирован, раунд подвис:** Admin отменяет через POST /cancel
6. **Функция удалена в Catalog во время согласования:** Не влияет — рецензенты видят зафиксированную версию
7. **Сколько раундов:** Без ограничений. Типично 2-4

## Audit Actions
- `approval.submit` — отправка (document_id, type, reviewers)
- `approval.decide` — решение (decision_type, comment)
- `approval.revoke` — отзыв (revoked_decision_type)
- `approval.round_closed` — раунд завершён (round_number, final_decision)
- `approval.cancel` — отмена (reason, cancelled_by)
- `document.locked` — блокировка
- `document.unlocked` — разблокировка

## Переменные окружения
```env
DB_HOST=workflow-postgres
DB_PORT=5432
DB_NAME=workflow_db
DB_USER=workflow_user
DB_PASSWORD=<secret>
AUTH_SERVICE_URL=http://auth-service:8001
INTERNAL_API_SECRET=<secret>
```

## Тесты

**Unit (round_evaluator):** все 9 комбинаций + неправильная роль + неправильная сторона + повторное решение

**Интеграционный:** create approval → review (аналитик) → revision (РП заказчика) → новый раунд → approve (РП заказчика) → approve (РП подрядчика) → assert status == approved, current_round == 2

## Структура кода
```
workflow-service/
  app/
    main.py
    config.py
    models/
      approval.py
    schemas/
      requests.py
      responses.py
    services/
      approval_service.py
      round_evaluator.py
      lock_manager.py
    api/
      approvals.py
      dashboard.py
      internal.py
    events/
      emitter.py            # emit_event() — log в MVP, Kafka в v2
  alembic/
    versions/
      001_approval_tables.py
  tests/
    test_round_evaluator.py
    test_approval_flow.py
  Dockerfile
  requirements.txt
```
