# Kafka и событийная архитектура (EDA) в системе ГОСТ 34

## Обзор

В системе используется Apache Kafka для асинхронного обмена сообщениями между микросервисами.  
Это позволяет сервисам взаимодействовать без прямой зависимости друг от друга (слабая связанность).

До внедрения Kafka workflow-сервис уведомлял catalog-сервис о блокировке документов через HTTP-вызов
на эндпоинт `/internal/documents/{id}/status`. Этот эндпоинт в catalog-сервисе не был реализован,
поэтому вызовы молча падали. Kafka заменяет этот механизм надёжным асинхронным каналом.

---

## Инфраструктура

### Брокер

| Параметр | Значение |
|---|---|
| Образ | `bitnami/kafka:3.7` |
| Режим | KRaft (без ZooKeeper) |
| Адрес внутри Docker-сети | `kafka:9092` |
| Автоматическое создание топиков | включено |

**KRaft** — встроенный механизм консенсуса Kafka (с версии 3.3+), не требующий отдельного
кластера ZooKeeper. Упрощает развёртывание: нет лишнего сервиса, нет проблемы синхронизации.

### Kafka UI

Веб-интерфейс для просмотра топиков и сообщений: **http://localhost:9080**

---

## Топики

### `gost34.workflow.events`

Все события жизненного цикла согласований и блокировок документов.

**Producer:** workflow-service  
**Consumer:** catalog-service

---

## Типы событий

### `approval.submitted` — согласование отправлено

Emitтируется когда пользователь отправляет документ на согласование.

```json
{
  "event_type": "approval.submitted",
  "service": "workflow",
  "timestamp": "2026-04-02T13:00:00.000Z",
  "approval_id": "uuid",
  "document_id": "uuid",
  "project_id": "uuid",
  "approval_type": "tz_final",
  "initiated_by": "uuid пользователя"
}
```

---

### `approval.completed` — раунд согласования завершён

Emitтируется когда оба РП (заказчика и подрядчика) приняли решение в текущем раунде
и система вычислила итоговый исход.

```json
{
  "event_type": "approval.completed",
  "service": "workflow",
  "timestamp": "2026-04-02T14:00:00.000Z",
  "approval_id": "uuid",
  "document_id": "uuid",
  "project_id": "uuid",
  "outcome": "approved | rejected | revision",
  "round_number": 1
}
```

---

### `approval.cancelled` — согласование отменено

Emitтируется когда ПМ или администратор отменяет активное согласование.

```json
{
  "event_type": "approval.cancelled",
  "service": "workflow",
  "timestamp": "2026-04-02T14:30:00.000Z",
  "approval_id": "uuid",
  "document_id": "uuid",
  "project_id": "uuid",
  "cancelled_by": "uuid пользователя"
}
```

---

### `document.locked` — документ заблокирован

Emitтируется одновременно с `approval.submitted` для документов типа `tz_final` и `nmck_final`.  
Означает: документ нельзя редактировать, пока идёт согласование.

```json
{
  "event_type": "document.locked",
  "service": "workflow",
  "timestamp": "2026-04-02T13:00:00.000Z",
  "document_id": "uuid",
  "locked": true,
  "document_status": "pending",
  "approval_id": "uuid"
}
```

---

### `document.unlocked` — документ разблокирован

Emitтируется когда согласование завершилось (кроме `approved`) или было отменено.

```json
{
  "event_type": "document.unlocked",
  "service": "workflow",
  "timestamp": "2026-04-02T14:00:00.000Z",
  "document_id": "uuid",
  "locked": false,
  "document_status": "draft | rejected",
  "approval_id": "uuid"
}
```

---

## Поток данных

```
Пользователь
    │
    ▼
workflow-service
    │  submit_approval()
    │  ├── Kafka: approval.submitted
    │  └── Kafka: document.locked
    │
    │  decide()  (оба РП приняли решение)
    │  ├── Kafka: approval.completed
    │  └── Kafka: document.locked / document.unlocked
    │
    │  cancel_approval()
    │  ├── Kafka: approval.cancelled
    │  └── Kafka: document.unlocked
    │
    ▼
Топик: gost34.workflow.events
    │
    ▼
catalog-service (consumer group: catalog-service)
    │  kafka_consumer.py
    │  ├── document.locked   → Document.locked = True,  status = "pending"
    │  └── document.unlocked → Document.locked = False, status = "draft" | "rejected"
    │
    ▼
MongoDB (коллекция documents)
```

---

## Реализация

### Producer (workflow-service)

**Файл:** `shared/shared/services/events.py`

```python
class EventEmitter:
    async def emit(self, event_type, payload, topic, key=None):
        # Отправляет сообщение в Kafka
        # При недоступности Kafka — пишет в лог и продолжает работу (graceful fallback)
```

Продюсер создаётся один раз при старте сервиса (`lifespan` в `main.py`) и переиспользуется
для всех запросов. Используется `send_and_wait` — ждём подтверждения от брокера.

**Ключ сообщения:** `document_id` — гарантирует порядок событий для одного документа
(сообщения с одним ключом всегда попадают в одну партицию).

### Consumer (catalog-service)

**Файл:** `catalog-service/app/services/kafka_consumer.py`

```python
async def _consume_loop(bootstrap_servers):
    consumer = AIOKafkaConsumer(TOPIC, group_id="catalog-service", ...)
    async for msg in consumer:
        await _process_message(msg)
```

Consumer запускается как фоновая задача (`asyncio.create_task`) при старте catalog-сервиса
и работает всё время жизни приложения.

**Consumer group:** `catalog-service` — если запустить несколько экземпляров catalog-сервиса,
каждое сообщение будет обработано ровно одним из них (балансировка через Kafka).

---

## Graceful degradation

Kafka не является критическим компонентом для основных бизнес-операций:

- Если Kafka недоступна при старте — **сервисы запускаются** (продюсер пытается подключиться лениво)
- Если `emit()` падает — **ошибка логируется**, запрос пользователя завершается успешно
- Если consumer не может подключиться — **повторяет попытку каждые 5 секунд**

Состояние документа (`locked`, `status`) в MongoDB является вторичным по отношению к состоянию
в workflow-сервисе. Если событие блокировки не дошло до catalog — следующая попытка чтения
документа покажет устаревший статус, но согласование продолжится корректно.

---

## Мониторинг

Kafka UI доступен по адресу **http://localhost:9080** и позволяет:

- Просматривать список топиков и партиций
- Читать сообщения в топике `gost34.workflow.events`
- Видеть consumer groups и их lag (отставание от конца топика)
- Проверять, обрабатывает ли catalog-сервис сообщения в реальном времени

---

## Consumer lag

**Lag** — количество сообщений в топике, которые ещё не обработал consumer.  
В норме lag для группы `catalog-service` должен быть равен 0 (нет отставания).  
Если lag растёт — catalog-сервис не успевает обрабатывать события (проблема производительности или падение).

---

## Расширение в будущем (v2)

| Что добавить | Зачем |
|---|---|
| Топик `gost34.auth.events` | Уведомления при создании/деактивации пользователей |
| Топик `gost34.generation.events` | Подтверждение генерации документа |
| Schema Registry (Confluent) | Валидация схемы сообщений, предотвращение breaking changes |
| Dead Letter Queue (DLQ) | Сообщения, которые consumer не смог обработать, не теряются |
| Kafka Connect | Стриминг данных из PostgreSQL/MongoDB в аналитическое хранилище |
| Несколько партиций | Горизонтальное масштабирование consumer-группы |
