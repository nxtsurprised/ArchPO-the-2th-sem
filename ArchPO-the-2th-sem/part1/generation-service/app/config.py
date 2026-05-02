from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # External services
    CATALOG_SERVICE_URL: str = "http://catalog-service:8002"
    AUTH_SERVICE_URL: str = "http://auth-service:8001"

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "documents"
    MINIO_TEMPLATES_BUCKET: str = "templates"
    MINIO_SECURE: bool = False
    PRESIGNED_URL_EXPIRY: int = 900  # seconds

    # Internal API
    INTERNAL_API_SECRET: str = "internal_secret"

    # Redis (опционально — fallback на in-memory если не задан)
    REDIS_URL: str | None = None

    # Холодное хранилище
    MINIO_ARCHIVE_BUCKET: str = "documents-archive"
    ARCHIVE_AFTER_DAYS: int = 90    # документы старше N дней переводятся в cold storage
    ARCHIVE_INTERVAL_HOURS: int = 24  # как часто запускать воркер архивирования

    # Local .dotx fallback (for dev/tests without MinIO)
    # If set, Generation Service reads template from this path instead of MinIO.
    DOTX_LOCAL_PATH: str | None = None

    # App
    APP_VERSION: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
