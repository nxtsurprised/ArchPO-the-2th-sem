"""
Kafka consumer for catalog-service.

Listens to gost34.workflow.events and processes:
  - document.locked   → set document status + locked=True  in MongoDB
  - document.unlocked → set document status + locked=False in MongoDB

Runs as a background asyncio task started in app lifespan.
"""
import asyncio
import json
from typing import Any
import structlog

logger = structlog.get_logger()

TOPIC = "gost34.workflow.events"
GROUP_ID = "catalog-service"

_consumer_task: asyncio.Task | None = None


async def _process_message(msg: Any) -> None:
    try:
        data: dict = json.loads(msg.value)
    except Exception:
        logger.warning("kafka_invalid_message", raw=msg.value)
        return

    event_type = data.get("event_type")
    document_id = data.get("document_id")

    if event_type not in ("document.locked", "document.unlocked"):
        return  # not for us

    if not document_id:
        logger.warning("kafka_missing_document_id", event_type=event_type)
        return

    locked = event_type == "document.locked"
    new_status = data.get("document_status", "pending" if locked else "draft")

    try:
        from app.models.document import Document
        doc = await Document.get(document_id)
        if doc is None:
            logger.warning("kafka_document_not_found", document_id=document_id)
            return

        doc.locked = locked
        doc.status = new_status
        await doc.save()

        logger.info(
            "document_lock_applied",
            document_id=document_id,
            locked=locked,
            status=new_status,
            approval_id=data.get("approval_id"),
        )
    except Exception as e:
        logger.error("kafka_document_update_failed", document_id=document_id, error=str(e))


async def _consume_loop(bootstrap_servers: str) -> None:
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=bootstrap_servers,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: v,  # raw bytes; we parse manually
    )

    # Retry connecting — Kafka may not be ready immediately
    while True:
        try:
            await consumer.start()
            logger.info("kafka_consumer_started", topic=TOPIC, group=GROUP_ID)
            break
        except Exception as e:
            logger.warning("kafka_consumer_connect_retry", error=str(e))
            await asyncio.sleep(5)

    try:
        async for msg in consumer:
            await _process_message(msg)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("kafka_consumer_error", error=str(e))
    finally:
        await consumer.stop()
        logger.info("kafka_consumer_stopped")


def start_consumer(bootstrap_servers: str) -> None:
    """Start the consumer as a background task (call from app lifespan)."""
    global _consumer_task
    _consumer_task = asyncio.create_task(_consume_loop(bootstrap_servers))


async def stop_consumer() -> None:
    """Cancel the consumer task (call from app lifespan shutdown)."""
    global _consumer_task
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
