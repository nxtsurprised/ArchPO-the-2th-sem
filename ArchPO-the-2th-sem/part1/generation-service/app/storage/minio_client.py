from __future__ import annotations
import asyncio
import hashlib
import io
import time
from datetime import timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class MinioClient:
    """
    Обёртка над minio-py для асинхронного использования.

    minio-py — синхронная библиотека. Прямой вызов из async-кода заблокировал бы
    event loop на время сетевого запроса. Поэтому все операции запускаются через
    loop.run_in_executor(None, ...) — выполняются в пуле потоков ThreadPoolExecutor,
    не блокируя event loop.

    Реализует:
    - put_object       — загрузка с вычислением SHA-256
    - presigned_get    — presigned URL на скачивание (для API /download)
    - get_object_bytes — скачивание в память (для .dotx шаблонов)
    - list_objects_by_prefix — список файлов по префиксу (для архивного воркера)
    - copy_to_archive  — перемещение из hot в cold bucket
    - 3 retry с экспоненциальной задержкой (1s, 2s, 4s) через _with_retry
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # секунды

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        templates_bucket: str,
        archive_bucket: str = "documents-archive",
        secure: bool = False,
        presigned_expiry: int = 900,
    ) -> None:
        from minio import Minio

        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket = bucket
        self.templates_bucket = templates_bucket
        self.archive_bucket = archive_bucket
        self.presigned_expiry = presigned_expiry

        self._ensure_bucket(bucket)
        self._ensure_bucket(templates_bucket)
        self._ensure_bucket(archive_bucket)

    def _ensure_bucket(self, bucket: str) -> None:
        """Создаёт bucket если не существует."""
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
        except Exception as exc:
            logger.warning("minio_bucket_ensure_failed", bucket=bucket, error=str(exc))

    # ──────────────────────────────────────────────────────────────────────────

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Загружает объект и возвращает SHA-256 контрольную сумму."""
        checksum = hashlib.sha256(data).hexdigest()
        await self._with_retry(self._sync_put, key, data, content_type)
        return checksum

    def _sync_put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    async def presigned_get_url(self, key: str) -> str:
        """Возвращает presigned URL для скачивания объекта."""
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(seconds=self.presigned_expiry),
            ),
        )
        return url

    async def get_object_bytes(self, bucket: str, key: str) -> bytes | None:
        """Скачивает объект и возвращает байты, или None если не найден."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self._client.get_object(bucket, key)
            )
            return response.read()
        except Exception as exc:
            logger.warning("minio_get_object_failed", key=key, error=str(exc))
            return None

    async def stat_object(self, key: str) -> dict | None:
        """Возвращает метаданные объекта или None если не найден."""
        try:
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(
                None, lambda: self._client.stat_object(self.bucket, key)
            )
            return {"size": stat.size, "etag": stat.etag}
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────

    async def list_objects_by_prefix(self, prefix: str) -> list[dict]:
        """
        Возвращает список объектов в hot bucket с заданным префиксом.
        Каждый элемент: {"key": str, "size": int, "last_modified": datetime}
        """
        loop = asyncio.get_event_loop()
        try:
            objects = await loop.run_in_executor(
                None,
                lambda: list(self._client.list_objects(self.bucket, prefix=prefix, recursive=True)),
            )
            return [
                {
                    "key": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                }
                for obj in objects
            ]
        except Exception as exc:
            logger.warning("minio_list_objects_failed", prefix=prefix, error=str(exc))
            return []

    async def copy_to_archive(self, key: str) -> str:
        """
        Копирует объект из documents bucket в documents-archive bucket.
        Возвращает ключ объекта в archive bucket (идентичен исходному).
        После успешного копирования удаляет объект из hot bucket.
        """
        from minio.commonconfig import CopySource

        loop = asyncio.get_event_loop()

        def _do_copy():
            self._client.copy_object(
                self.archive_bucket,
                key,
                CopySource(self.bucket, key),
            )

        await self._with_retry(_do_copy)

        # Удаляем из hot bucket только после подтверждения копирования
        try:
            await loop.run_in_executor(
                None, lambda: self._client.remove_object(self.bucket, key)
            )
            logger.info("archive_hot_deleted", key=key, bucket=self.bucket)
        except Exception as exc:
            # Не фатально: объект уже скопирован, удаление можно повторить позже
            logger.warning("archive_hot_delete_failed", key=key, error=str(exc))

        logger.info("archive_copied", key=key, src=self.bucket, dst=self.archive_bucket)
        return key

    async def _with_retry(self, fn, *args) -> Any:
        """Выполняет синхронную функцию с 3 retry и экспоненциальной задержкой."""
        loop = asyncio.get_event_loop()
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return await loop.run_in_executor(None, lambda: fn(*args))
            except Exception as exc:
                last_exc = exc
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "minio_retry",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
        raise RuntimeError(f"MinIO unavailable after {self.MAX_RETRIES} retries: {last_exc}") from last_exc


# Синглтон — один клиент на весь процесс сервиса.
# Инициализируется через init_minio() в lifespan при старте,
# получается через get_minio_client() из любого места кода.
_minio: MinioClient | None = None


def get_minio_client() -> MinioClient:
    if _minio is None:
        raise RuntimeError("MinioClient not initialized")
    return _minio


def init_minio(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    templates_bucket: str,
    archive_bucket: str,
    secure: bool,
    presigned_expiry: int,
) -> MinioClient:
    global _minio
    _minio = MinioClient(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        templates_bucket=templates_bucket,
        archive_bucket=archive_bucket,
        secure=secure,
        presigned_expiry=presigned_expiry,
    )
    return _minio
