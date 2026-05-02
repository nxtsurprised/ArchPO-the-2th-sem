"""RAG — Retrieval-Augmented Generation для PMI-агента."""

import structlog
from sentence_transformers import SentenceTransformer

from .chromadb_client import ChromaDBClient, COLLECTION_KNOWLEDGE

logger = structlog.get_logger(__name__)

# Multilingual модель — понимает русский и английский
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Singleton embedder."""
    global _embedder
    if _embedder is None:
        logger.info("loading_embedding_model", model=EMBEDDING_MODEL)
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("embedding_model_loaded")
    return _embedder


class RAGRetriever:
    """
    Извлекает релевантный контекст из knowledge base для промптов агентов.
    """

    def __init__(self, n_results: int = 5) -> None:
        self._db = ChromaDBClient()
        self._embedder = get_embedder()
        self._n_results = n_results

    def retrieve(
        self,
        query: str,
        source_filter: str | None = None,
    ) -> str:
        """
        Поиск релевантных чанков по запросу.

        Args:
            query: Текст запроса (описание функции, название шага и т.п.)
            source_filter: Имя файла знаний для фильтрации (напр. "gost_34603")

        Returns:
            Конкатенированный текст релевантных чанков.
        """
        embedding = self._embedder.encode([query], normalize_embeddings=True).tolist()

        where = {"source": source_filter} if source_filter else None

        try:
            results = self._db.query(
                collection_name=COLLECTION_KNOWLEDGE,
                query_embeddings=embedding,
                n_results=self._n_results,
                where=where,
            )
        except Exception as e:
            logger.warning("rag_retrieval_failed", error=str(e))
            return ""

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if not docs:
            return ""

        parts: list[str] = []
        for doc, meta in zip(docs, metas):
            source = meta.get("source", "unknown")
            parts.append(f"[{source}]\n{doc}")

        context = "\n\n---\n\n".join(parts)
        logger.debug("rag_retrieved", query_len=len(query), chunks=len(docs))
        return context

    def retrieve_for_planner(self, function_description: str) -> str:
        """RAG-контекст для агента Планировщика."""
        queries = [
            function_description,
            "метод испытания ГОСТ 34.603 проверка демонстрация тестирование",
            "паттерн тест-план шаги",
        ]
        parts: list[str] = []
        seen: set[str] = set()

        for q in queries:
            result = self.retrieve(q)
            if result and result not in seen:
                parts.append(result)
                seen.add(result)

        return "\n\n===\n\n".join(parts)

    def retrieve_for_executor(self, step_description: str) -> str:
        """RAG-контекст для агента Исполнителя."""
        return self.retrieve(
            f"CSS-селектор элемент {step_description}",
            source_filter="selector_strategies",
        )

    def retrieve_for_writer(self, function_name: str) -> str:
        """RAG-контекст для агента Протоколиста."""
        queries = [
            f"результат испытания {function_name}",
            "вердикт соответствует не соответствует ПМИ",
            "наблюдения протокол испытаний",
        ]
        parts: list[str] = []
        for q in queries:
            result = self.retrieve(q)
            if result:
                parts.append(result)

        return "\n\n===\n\n".join(parts)
