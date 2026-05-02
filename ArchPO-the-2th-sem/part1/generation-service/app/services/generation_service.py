"""
Оркестратор шести этапов генерации документа.

Пайплайн (вызывается для каждого Job фоновой asyncio-задачей):

  Этап 1 — Получить render-bundle от catalog-service
           (шаблон + данные секций + функции + подсистемы + ставки)
  Этап 2 — Валидация bundle: все обязательные поля заполнены?
           → failed если нет
  Этап 3 — Рендер секций в промежуточное представление (IR-элементы)
           → для .docx: manual/functions/subsystems/static секции
           → для .xlsx: только НМЦК-расчёт через XlsxBuilder
  Этап 4 — Форматирование по ГОСТ 2.105 через DocxBuilder / XlsxBuilder
           (открывает .dotx шаблон, применяет именованные стили)
  Этап 5 — Сохранение в MinIO с 3 retry и расчётом SHA-256
  Этап 6 — Best-effort обратная связь: PATCH Catalog с номерами разделов ТЗ

Job изменяется in-place (status, progress, file_key, checksum, error).
Все этапы работают в одной фоновой asyncio-задаче — не нужна синхронизация.
"""
from __future__ import annotations
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import structlog

from app.config import get_settings
from app.models.job import Job
from app.pipeline.validator import BundleValidator
from app.pipeline.section_renderer import render_section
from app.pipeline.formatters.docx_builder import DocxBuilder
from app.pipeline.formatters.xlsx_builder import XlsxBuilder

logger = structlog.get_logger()

_validator = BundleValidator()

# Дефолтный шаблон ГОСТ 2.105, поставляется в образе сервиса.
# Используется если в шаблоне Catalog не задан dotx_key или MinIO недоступен.
_DEFAULT_DOTX = Path(__file__).parent.parent.parent / "assets" / "gost-2105-template.dotx"


async def _fetch_render_bundle(document_id: str) -> dict:
    """Запрашивает render-bundle у Catalog Service."""
    settings = get_settings()
    url = f"{settings.CATALOG_SERVICE_URL}/internal/documents/{document_id}/render-bundle"
    headers = {"X-Internal-Secret": settings.INTERNAL_API_SECRET}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def _load_dotx(minio_client, dotx_key: str | None) -> bytes | None:
    """
    Загружает .dotx шаблон.

    Порядок приоритетов:
    1. Пользовательский ключ из MinIO (если задан в шаблоне).
    2. Дефолтный ГОСТ 2.105 из assets/ (поставляется в образе).
    """
    # Пользовательский шаблон из MinIO
    if dotx_key:
        try:
            data = await minio_client.get_object_bytes(minio_client.templates_bucket, dotx_key)
            if data:
                logger.info("dotx_loaded_from_minio", key=dotx_key)
                return data
        except Exception as exc:
            logger.warning("dotx_minio_fetch_failed", key=dotx_key, error=str(exc))

    # Дефолтный шаблон из файловой системы контейнера
    try:
        data = _DEFAULT_DOTX.read_bytes()
        logger.info("dotx_loaded_from_assets", path=str(_DEFAULT_DOTX))
        return data
    except Exception as exc:
        logger.warning("dotx_assets_load_failed", path=str(_DEFAULT_DOTX), error=str(exc))
        return None


async def run_generation_pipeline(job: Job) -> None:
    """
    Оркестратор шести этапов генерации.
    Изменяет job in-place. Вызывается в фоновом asyncio-задании из jobs API.
    """
    # Отложенный импорт — избегает циклической зависимости при инициализации модуля
    from app.services.audit_store import record_audit
    from app.storage.minio_client import get_minio_client

    t_start = time.monotonic()
    minio = get_minio_client()
    settings = get_settings()

    try:
        job.status = "processing"
        job.progress = 0
        record_audit("generation.start", document_id=job.document_id, format=job.format, job_id=job.id)

        # ── Этап 1: Получить render-bundle ────────────────────────────────────
        # Один HTTP-запрос возвращает всё необходимое: шаблон, данные секций,
        # справочник функций, подсистемы, ставки и информацию о проекте.
        bundle = await _fetch_render_bundle(job.document_id)
        job.progress = 10

        # ── Этап 2: Валидация ─────────────────────────────────────────────────
        result = _validator.validate(bundle)
        job.warnings.extend(result.warnings)  # предупреждения (не блокируют генерацию)

        if not result.is_valid:
            job.status = "failed"
            job.error = "Missing required fields: " + ", ".join(result.missing_fields)
            job.completed_at = datetime.now(timezone.utc)
            logger.error("generation_validation_failed", job_id=job.id, missing=result.missing_fields)
            record_audit("generation.failed", job_id=job.id, error_type="validation", message=job.error)
            return

        job.progress = 20

        # ── Этапы 3–4: Рендер секций + форматирование ────────────────────────
        # _render_docx обновляет job.progress (20→80) по мере обработки секций
        if job.format == "docx":
            file_bytes = await _render_docx(job, bundle, minio)
        else:
            file_bytes = _render_xlsx(bundle)

        job.progress = 80

        # ── Этап 5: Сохранение в MinIO ────────────────────────────────────────
        # file_key: projects/{project_id}/docs/{document_id}/{job_id}.{ext}
        # Воркер холодного хранилища находит файл по префиксу projects/.../docs/{doc_id}/
        project_id = bundle.get("project", {}).get("id", "unknown")
        ext = job.format
        file_key = f"projects/{project_id}/docs/{job.document_id}/{job.id}.{ext}"
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if ext == "docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        checksum = await minio.put_object(file_key, file_bytes, content_type)

        job.file_key = file_key
        job.checksum = checksum
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)

        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "generation_complete",
            job_id=job.id,
            file_key=file_key,
            checksum=checksum,
            duration_ms=duration_ms,
        )
        record_audit("generation.complete", job_id=job.id, file_key=file_key,
                     checksum=checksum, duration_ms=duration_ms)

        # ── Этап 6: Обратная связь (best-effort) ─────────────────────────────
        # Не ждём результата (create_task, не await) — сбой этапа не отменяет
        # успешно сохранённый файл и не меняет статус job.
        asyncio.create_task(_update_doc_refs(bundle, job))

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        logger.exception("generation_failed", job_id=job.id, error=str(exc))
        record_audit("generation.failed", job_id=job.id, error_type="exception", message=str(exc))


async def _render_docx(job: Job, bundle: dict, minio) -> bytes:
    """Этапы 3–4 для .docx: рендер всех секций → IR-элементы → DocxBuilder → байты."""
    template = bundle.get("template", {})
    sections = template.get("sections", [])

    dotx_key = bundle.get("dotx_key") or None
    dotx_bytes = await _load_dotx(minio, dotx_key)

    all_elements = []
    total_sections = len(sections)

    # Рендерим секции одну за другой, обновляя progress (диапазон 20%→80%)
    for idx, section in enumerate(sections):
        elements = render_section(section, bundle)
        all_elements.extend(elements)
        if total_sections > 0:
            job.progress = 20 + int(60 * (idx + 1) / total_sections)

    # DocxBuilder применяет именованные стили из .dotx или программный fallback
    builder = DocxBuilder(dotx_bytes=dotx_bytes)
    return builder.build(all_elements)


def _render_xlsx(bundle: dict) -> bytes:
    """Этапы 3–4 для .xlsx: НМЦК."""
    functions = bundle.get("functions", [])
    subsystems = bundle.get("subsystems", [])
    rates = bundle.get("rates", {})

    builder = XlsxBuilder()
    return builder.build(functions, subsystems, rates)


async def _update_doc_refs(bundle: dict, job: Job) -> None:
    """
    Этап 6: best-effort PATCH в Catalog с обновлением ссылок на разделы ТЗ.

    После генерации каждая функция получает номер раздела (например "4.2.1"),
    чтобы в Catalog можно было видеть, в каком разделе документа она описана.
    Только для .docx — в .xlsx нет структуры разделов.
    """
    settings = get_settings()
    functions = bundle.get("functions", [])
    subsystems = bundle.get("subsystems", [])

    if not functions or job.format != "docx":
        return

    # Строим маппинг func_id → номер раздела ТЗ по позиции подсистемы
    refs = []
    sorted_subs = sorted(subsystems, key=lambda s: s.get("order", 0))
    sub_index = {s["id"]: idx + 1 for idx, s in enumerate(sorted_subs)}

    for func in functions:
        sub_idx = sub_index.get(func.get("subsystem_id", ""), 0)
        tz_section = f"4.2.{sub_idx}" if sub_idx else "4.2"
        refs.append({"func_id": func["id"], "doc_refs.tz_section": tz_section})

    try:
        url = f"{settings.CATALOG_SERVICE_URL}/internal/functions/batch-update-refs"
        headers = {"X-Internal-Secret": settings.INTERNAL_API_SECRET}
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(url, json=refs, headers=headers)
    except Exception as exc:
        logger.warning("batch_update_refs_failed", error=str(exc))
