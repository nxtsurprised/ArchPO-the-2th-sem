from __future__ import annotations
import structlog

logger = structlog.get_logger()


class EventEmitter:
    """
    MVP: structlog.info(event=name, **payload)
    v2: kafka.produce(topic=name, value=payload)
    """

    async def emit(self, event_name: str, payload: dict) -> None:
        logger.info("event_emitted", event=event_name, **payload)
