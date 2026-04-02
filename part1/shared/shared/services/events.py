import json
import asyncio
from datetime import datetime, timezone
from typing import Any
import structlog

logger = structlog.get_logger()

_producer = None
_producer_lock = asyncio.Lock()
_bootstrap_servers: str = "kafka:9092"
_service_name: str = "unknown"


def configure(bootstrap_servers: str, service_name: str) -> None:
    """Call once at app startup before first emit."""
    global _bootstrap_servers, _service_name
    _bootstrap_servers = bootstrap_servers
    _service_name = service_name


async def _get_producer():
    global _producer
    async with _producer_lock:
        if _producer is None:
            from aiokafka import AIOKafkaProducer
            candidate = AIOKafkaProducer(
                bootstrap_servers=_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                key_serializer=lambda k: k.encode() if k else None,
                request_timeout_ms=5000,
                retry_backoff_ms=500,
            )
            await candidate.start()  # raises on failure — _producer stays None
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
    Kafka producer wrapper. Emits structured events to a topic.

    Falls back to structlog.info() if Kafka is unavailable so business
    logic is never blocked by messaging infrastructure.
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
            # Graceful degradation: log and continue, never break the request
            logger.warning("event_emit_failed", event_type=event_type, error=str(e))
