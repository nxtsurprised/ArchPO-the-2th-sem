from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "workflow_db"
    DB_USER: str = "workflow_user"
    DB_PASSWORD: str = "workflow_pass"

    JWKS_URL: str | None = None
    JWT_PUBLIC_KEY_PATH: str | None = None

    INTERNAL_API_SECRET: str = "internal_secret"
    CATALOG_INTERNAL_URL: str = "http://catalog-service:8002"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
