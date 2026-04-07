from __future__ import annotations
import asyncio
import hashlib
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.job_manager import get_job_manager
from app.services.generation_service import run_generation_pipeline

logger = structlog.get_logger()
router = APIRouter(prefix="/api/generation", tags=["generation"])


class StartJobRequest(BaseModel):
    document_id: str
    format: Literal["docx", "xlsx"]


# ── POST /api/generation/jobs ──────────────────────────────────────────────────

@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    body: StartJobRequest,
    user=Depends(get_current_user),
):
    """
    Запускает генерацию документа.
    Idempotency: если уже есть pending/processing для document_id+format — возвращает его.
    """
    manager = get_job_manager()
    job = await manager.create(
        document_id=body.document_id,
        fmt=body.format,
        user_id=str(user.sub),
    )

    if job.status == "pending":
        # Запускаем пайплайн в фоне
        asyncio.create_task(run_generation_pipeline(job))
        logger.info("generation_start", job_id=job.id, document_id=body.document_id, format=body.format)

    return {"job_id": job.id, "status": job.status}


# ── GET /api/generation/jobs/:job_id ──────────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user=Depends(get_current_user),
):
    """Статус job-а: pending → processing → completed / failed."""
    manager = get_job_manager()
    job = await manager.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"},
        )
    return job.to_dict()


# ── GET /api/generation/jobs/:job_id/download ─────────────────────────────────

@router.get("/jobs/{job_id}/download")
async def download_job(
    job_id: str,
    user=Depends(get_current_user),
):
    """
    Стримит файл напрямую через generation-service.
    Проверяет SHA-256 целостность файла.
    """
    import io
    from fastapi.responses import StreamingResponse
    from app.storage.minio_client import get_minio_client

    manager = get_job_manager()
    job = await manager.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"},
        )

    if job.status != "completed" or not job.file_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "JOB_NOT_COMPLETED", "message": f"Job status: {job.status}"},
        )

    minio = get_minio_client()

    file_bytes = await minio.get_object_bytes(minio.bucket, job.file_key)
    if file_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_NOT_FOUND", "message": "File not found in storage"},
        )

    actual_checksum = hashlib.sha256(file_bytes).hexdigest()
    if actual_checksum != job.checksum:
        logger.error(
            "checksum_mismatch",
            job_id=job_id,
            expected=job.checksum,
            actual=actual_checksum,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CHECKSUM_MISMATCH", "message": "File integrity check failed"},
        )

    logger.info("generation_download", job_id=job_id, file_key=job.file_key)
    from app.services.audit_store import record_audit
    record_audit("generation.download", job_id=job_id, file_key=job.file_key)

    ext = job.file_key.rsplit(".", 1)[-1] if "." in job.file_key else "docx"
    content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == "xlsx"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    filename = job.file_key.rsplit("/", 1)[-1]

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /api/generation/documents/:document_id/files ─────────────────────────

@router.get("/documents/{document_id}/files")
async def list_document_files(
    document_id: str,
    user=Depends(get_current_user),
):
    """История генераций для документа."""
    from app.storage.minio_client import get_minio_client

    manager = get_job_manager()
    jobs = await manager.list_by_document(document_id)
    completed = [j for j in jobs if j.status == "completed"]

    result = []
    minio = get_minio_client()
    for job in completed:
        stat = await minio.stat_object(job.file_key) if job.file_key else None
        result.append({
            "job_id": job.id,
            "format": job.format,
            "created_at": job.created_at.isoformat(),
            "file_size": stat["size"] if stat else None,
            "checksum": job.checksum,
        })

    return result
