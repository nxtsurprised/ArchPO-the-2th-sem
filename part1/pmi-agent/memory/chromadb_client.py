"""ChromaDB клиент — singleton для всего приложения."""

from __future__ import annotations

from typing import Any, Optional

import structlog
import chromadb
from chromadb.config import Settings

from config import settings

logger = structlog.get_logger(__name__)

_client: Optional[Any] = None

# Имена коллекций
COLLECTION_KNOWLEDGE = "pmi_knowledge"   # knowledge base (.md файлы)
COLLECTION_RESULTS   = "pmi_results"     # история результатов (few-shot)


def get_chroma_client() -> Any:
    """Возвращает singleton-клиент ChromaDB."""
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=settings.chroma_token,
            ),
        )
        logger.info("chromadb_connected", host=settings.chroma_host, port=settings.chroma_port)
    return _client


class ChromaDBClient:
    """Обёртка над ChromaDB для работы с коллекциями PMI-агента."""

    def __init__(self) -> None:
        self._client = get_chroma_client()

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> None:
        collection = self.get_or_create_collection(collection_name)
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )
        logger.info(
            "documents_upserted",
            collection=collection_name,
            count=len(documents),
        )

    def query(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        collection = self.get_or_create_collection(collection_name)
        return collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def count(self, collection_name: str) -> int:
        try:
            collection = self.get_or_create_collection(collection_name)
            return collection.count()
        except Exception:
            return 0
