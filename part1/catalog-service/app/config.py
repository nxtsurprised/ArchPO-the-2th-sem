from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB: str = "catalog_db"
    MONGO_USER: str = "catalog_user"
    MONGO_PASSWORD: str = "catalog_secret"

    @property
    def MONGO_URL(self) -> str:
        if self.MONGO_USER and self.MONGO_PASSWORD:
            return (
                f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}"
                f"@{self.MONGO_HOST}:{self.MONGO_PORT}"
            )
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

    # JWT verification — either JWKS_URL (prod) or JWT_PUBLIC_KEY_PATH (dev/tests)
    # In prod, point to Auth Service: http://auth-service:8001/.well-known/jwks.json
    JWKS_URL: str = ""
    JWT_PUBLIC_KEY_PATH: str = ""

    # Inter-service
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    WORKFLOW_SERVICE_URL: str = "http://workflow-service:8004"
    INTERNAL_API_SECRET: str = "internal_secret"

    # App
    APP_VERSION: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
