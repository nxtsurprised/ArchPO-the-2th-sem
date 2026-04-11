"""
Фоновый воркер холодного хранилища.

Каждые ARCHIVE_INTERVAL_HOURS часов:
  1. Запрашивает у catalog-service список документов, готовых к архивированию
     (статус approved/rejected, старше ARCHIVE_AFTER_DAYS дней, ещё не архивированы).
  2. Для каждого документа получает file_key из job-модели generation-service.
  3. Копирует файл из MinIO documents bucket → documents-archive bucket.
  4. Помечает документ архивированным через catalog internal API.

Если MinIO или catalog недоступны — воркер логирует ошибку и продолжает
работу при следующей итерации (graceful degradation).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import structlog

logger = structlog.get_logger()

_task: asyncio.Task | None = None


async def _archive_one(
    doc: dict,
    minio,
    catalog_url: str,
    internal_secret: str,
) -> bool:
    """
    Архивирует один документ.
    Возвращает True при успехе, False при любой ошибке.

    file_key неизвестен заранее (Job — in-memory, не персистентен).
    Находим файл по префиксу в MinIO: projects/{project_id}/docs/{doc_id}/
    Берём самый свежий объект (последняя генерация).
    """
    doc_id = doc["id"]
    doc_name = doc.get("name", "")
    project_id = doc.get("project_id", "")

    prefix = f"projects/{project_id}/docs/{doc_id}/"
    objects = await minio.list_objects_by_prefix(prefix)

    if not objects:
        logger.debug("archive_skip_no_file", document_id=doc_id, name=doc_name, prefix=prefix)
        return False

    # Берём самый свежий файл (на случай нескольких генераций одного документа)
    latest = max(objects, key=lambda o: o["last_modified"])
    file_key = latest["key"]

    try:
        archive_key = await minio.copy_to_archive(file_key)
    except Exception as exc:
        logger.warning("archive_copy_failed", document_id=doc_id, key=file_key, error=str(exc))
        return False

    archived_at = datetime.now(timezone.utc).isoformat()

    # Помечаем в catalog
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{catalog_url}/internal/documents/{doc_id}/archive",
                json={"archive_key": archive_key, "archived_at": archived_at},
                headers={"X-Internal-Secret": internal_secret},
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("archive_mark_failed", document_id=doc_id, error=str(exc))
        # Файл уже перемещён, но metadata не обновлена.
        # Это идемпотентная ситуация: при следующем запуске /archivable
        # не вернёт этот документ, если archived=True; но если каталог
        # не обновился — документ снова попадёт в список и скопирует уже
        # несуществующий ключ из hot bucket (безопасно — вернёт ошибку и пропустим).
        return False

    logger.info(
        "document_archived",
        document_id=doc_id,
        name=doc_name,
        archive_key=archive_key,
    )
    return True


async def _run_archive_cycle(
    catalog_url: str,
    internal_secret: str,
    archive_after_days: int,
) -> None:
    """Один цикл архивирования."""
    from app.storage.minio_client import get_minio_client

    try:
        minio = get_minio_client()
    except RuntimeError:
        logger.warning("archive_minio_not_ready")
        return

    # Получаем список кандидатов от catalog-service
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{catalog_url}/internal/documents/archivable",
                params={"days": archive_after_days, "limit": 200},
                headers={"X-Internal-Secret": internal_secret},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("archive_fetch_candidates_failed", error=str(exc))
        return

    candidates = data.get("items", [])
    if not candidates:
        logger.debug("archive_nothing_to_archive")
        return

    logger.info("archive_cycle_start", candidates=len(candidates), days=archive_after_days)

    archived = 0
    skipped = 0
    for doc in candidates:
        ok = await _archive_one(doc, minio, catalog_url, internal_secret)
        if ok:
            archived += 1
        else:
            skipped += 1

    logger.info("archive_cycle_done", archived=archived, skipped=skipped)


async def _loop(
    catalog_url: str,
    internal_secret: str,
    archive_after_days: int,
    interval_hours: int,
) -> None:
    """Бесконечный цикл с заданным интервалом."""
    logger.info(
        "archive_worker_started",
        archive_after_days=archive_after_days,
        interval_hours=interval_hours,
    )
    while True:
        try:
            await _run_archive_cycle(catalog_url, internal_secret, archive_after_days)
        except Exception as exc:
            logger.error("archive_cycle_error", error=str(exc))
        await asyncio.sleep(interval_hours * 3600)


def start_archive_worker(
    catalog_url: str,
    internal_secret: str,
    archive_after_days: int = 90,
    interval_hours: int = 24,
) -> None:
    """Запускает воркер как фоновую задачу asyncio. Вызывается из lifespan."""
    global _task
    _task = asyncio.create_task(
        _loop(catalog_url, internal_secret, archive_after_days, interval_hours),
        name="archive-worker",
    )


async def stop_archive_worker() -> None:
    """Останавливает воркер. Вызывается при shutdown."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    logger.info("archive_worker_stopped")
