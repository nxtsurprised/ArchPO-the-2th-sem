from __future__ import annotations
import asyncio
from typing import Literal

from app.models.job import Job


class JobManager:
    """
    In-memory хранилище job-ов.

    При перезапуске сервиса незавершённые job-ы теряются (приемлемо для MVP).
    Доступ защищён asyncio.Lock для корректной работы в многопоточном окружении.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, document_id: str, fmt: Literal["docx", "xlsx"], user_id: str) -> Job:
        """Создаёт новый job или возвращает существующий (idempotency)."""
        async with self._lock:
            # Idempotency: вернуть существующий job только если он ещё активен
            # (failed-джобы не переиспользуем — пользователь должен мочь попробовать снова)
            for job in self._jobs.values():
                if job.document_id == document_id and job.format == fmt and job.status != "failed":
                    return job

            job = Job(document_id=document_id, format=fmt, requested_by=user_id)
            self._jobs[job.id] = job
            return job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def list_by_document(self, document_id: str) -> list[Job]:
        return [j for j in self._jobs.values() if j.document_id == document_id]

    async def update(self, job: Job) -> None:
        """Сохраняет обновлённое состояние job-а (in-place, т.к. уже по ссылке)."""
        # Объект уже хранится по ссылке, достаточно убедиться, что он есть в словаре
        async with self._lock:
            self._jobs[job.id] = job


# Синглтон — разделяется между запросами через lifespan
_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager
