"""
Kafka producer для отправки событий между сервисами.

Паттерн — модульный синглтон:
  Один AIOKafkaProducer на весь процесс сервиса. Это эффективнее, чем создавать
  нового producer на каждый emit — producer держит постоянное TCP-соединение
  с брокером и внутренний буфер батчей.

  configure() вызывается один раз в lifespan при старте.
  stop_producer() вызывается в lifespan при завершении.

Ключ сообщения = document_id:
  Kafka гарантирует порядок сообщений в рамках одного partition.
  Используя document_id как ключ, все события одного документа попадают
  в один partition и обрабатываются consumer'ом строго по порядку.
  Это важно для корректности: document.locked → document.unlocked, а не наоборот.
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Any
import structlog

logger = structlog.get_logger()

_producer = None
# asyncio.Lock гарантирует, что при одновременных вызовах emit()
# producer инициализируется ровно один раз (защита от race condition при старте)
_producer_lock = asyncio.Lock()
_bootstrap_servers: str = "kafka:9092"
_service_name: str = "unknown"


def configure(bootstrap_servers: str, service_name: str) -> None:
    """Настраивает модуль. Вызывается один раз при старте приложения."""
    global _bootstrap_servers, _service_name
    _bootstrap_servers = bootstrap_servers
    _service_name = service_name


async def _get_producer():
    """Возвращает синглтон-producer, создавая его при первом вызове."""
    global _producer
    async with _producer_lock:
        if _producer is None:
            from aiokafka import AIOKafkaProducer
            candidate = AIOKafkaProducer(
                bootstrap_servers=_bootstrap_servers,
                # default=str позволяет сериализовать UUID, datetime и другие нестандартные типы
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                key_serializer=lambda k: k.encode() if k else None,
                request_timeout_ms=5000,
                retry_backoff_ms=500,
            )
            await candidate.start()  # при ошибке выбрасывает исключение — _producer остаётся None
            _producer = candidate
            logger.info("kafka_producer_started", servers=_bootstrap_servers)
    return _producer


async def stop_producer() -> None:
    """Call at app shutdown."""
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        except Exception:
            pass
        _producer = None


class EventEmitter:
    """
    Обёртка Kafka producer для отправки структурированных событий.

    Graceful degradation: если Kafka недоступна, событие логируется как warning
    и выполнение продолжается. Бизнес-операция (сохранение в БД) уже завершена —
    Kafka здесь ускоряющий элемент, а не критическая зависимость.
    """

    def __init__(self, service_name: str | None = None):
        self._service = service_name or _service_name

    async def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        topic: str = "gost34.workflow.events",
        key: str | None = None,
    ) -> None:
        """
        Отправляет событие в Kafka.

        key рекомендуется передавать как document_id — это гарантирует
        порядок обработки событий одного документа в consumer'е.

        send_and_wait (не send) ждёт подтверждения от брокера (ack),
        что гарантирует доставку сообщения в partition log.
        """
        message = {
            "event_type": event_type,
            "service": self._service,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        try:
            producer = await _get_producer()
            await producer.send_and_wait(topic, value=message, key=key)
            logger.info("event_emitted", event_type=event_type, topic=topic)
        except Exception as e:
            # Не прерываем запрос из-за недоступности Kafka
            logger.warning("event_emit_failed", event_type=event_type, error=str(e))
