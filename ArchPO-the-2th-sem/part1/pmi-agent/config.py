"""Конфигурация PMI Agent через переменные окружения."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="mistral:7b-instruct")
    ollama_timeout: int = Field(default=120)  # секунд

    # ChromaDB
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8005)
    chroma_token: str = Field(default="pmi-chroma-token")

    # Playwright (локальный Chromium внутри контейнера)
    playwright_timeout: int = Field(default=10000)  # мс

    # URL тестируемого фронтенда
    target_app_url: str = Field(default="http://localhost:8080")

    # Другие сервисы
    auth_service_url: str = Field(default="http://localhost:8001")
    catalog_service_url: str = Field(default="http://localhost:8002")
    generation_service_url: str = Field(default="http://localhost:8003")
    workflow_service_url: str = Field(default="http://localhost:8004")

    # Безопасность
    secret_key: str = Field(default="dev-secret-key")
    internal_api_secret: str = Field(default="internal_secret")

    # LangChain tracing
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")

    # Директории
    outputs_dir: str = Field(default="/app/outputs")

    # Логирование
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
