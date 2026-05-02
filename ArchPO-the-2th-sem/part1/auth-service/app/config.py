from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "auth_db"
    DB_USER: str = "auth_user"
    DB_PASSWORD: str = "auth_secret"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # JWT
    JWT_PRIVATE_KEY_PATH: str = "/run/secrets/jwt_private.pem"
    JWT_PUBLIC_KEY_PATH: str = "/run/secrets/jwt_public.pem"
    JWT_ACCESS_TTL_SECONDS: int = 900
    JWT_REFRESH_TTL_SECONDS: int = 604800
    JWT_ALGORITHM: str = "RS256"

    # Encryption
    ENCRYPT_KEY_PHONE: str = ""
    ENCRYPT_KEY_TOTP: str = ""

    # Password policy
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_HISTORY_SIZE: int = 10
    PASSWORD_EXPIRY_DAYS: int = 90

    # Argon2
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536

    # Login security
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_SECONDS: int = 1800
    MAX_CONCURRENT_SESSIONS: int = 3
    IDLE_TIMEOUT_SECONDS: int = 1800

    # Internal API
    INTERNAL_API_SECRET: str = "internal_secret"

    # SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@system.gov.ru"

    # App
    APP_VERSION: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
