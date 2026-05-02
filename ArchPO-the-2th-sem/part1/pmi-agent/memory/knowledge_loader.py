"""Загрузчик knowledge base из .md файлов в ChromaDB."""

import hashlib
import re
from pathlib import Path

import structlog

from .chromadb_client import ChromaDBClient, COLLECTION_KNOWLEDGE
from .rag import get_embedder

logger = structlog.get_logger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

# Размер чанка (символов) и перекрытие
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Разбивает текст на чанки с перекрытием, по возможности — по абзацам."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= size:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
                # Перекрытие: берём последние overlap символов предыдущего чанка
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + "\n\n" + para
            else:
                # Один параграф больше size — нарезаем принудительно
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
                current = ""

    if current:
        chunks.append(current)

    return chunks


def _doc_id(filename: str, chunk_index: int) -> str:
    """Детерминированный ID чанка."""
    return hashlib.md5(f"{filename}:{chunk_index}".encode()).hexdigest()


class KnowledgeLoader:
    """Загружает .md файлы из knowledge/ в ChromaDB при старте приложения."""

    def __init__(self) -> None:
        self._db = ChromaDBClient()
        self._embedder = get_embedder()

    def load_all(self, force: bool = False) -> int:
        """
        Загружает все .md файлы из knowledge/ в ChromaDB.

        Args:
            force: Если True — перезагрузить даже если данные уже есть.

        Returns:
            Количество загруженных чанков.
        """
        existing = self._db.count(COLLECTION_KNOWLEDGE)
        if existing > 0 and not force:
            logger.info("knowledge_already_loaded", chunks=existing)
            return existing

        md_files = list(KNOWLEDGE_DIR.glob("*.md"))
        if not md_files:
            logger.warning("no_knowledge_files_found", dir=str(KNOWLEDGE_DIR))
            return 0

        all_docs: list[str] = []
        all_metas: list[dict] = []
        all_ids: list[str] = []

        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            source = md_file.stem  # имя файла без .md
            chunks = _chunk_text(text)

            for idx, chunk in enumerate(chunks):
                all_docs.append(chunk)
                all_metas.append({"source": source, "chunk_index": idx})
                all_ids.append(_doc_id(source, idx))

            logger.info("file_chunked", file=md_file.name, chunks=len(chunks))

        if not all_docs:
            return 0

        # Вычисляем embeddings батчами по 64
        embeddings = self._embed_batched(all_docs, batch_size=64)

        self._db.upsert_documents(
            collection_name=COLLECTION_KNOWLEDGE,
            documents=all_docs,
            metadatas=all_metas,
            ids=all_ids,
            embeddings=embeddings,
        )

        logger.info("knowledge_loaded", total_chunks=len(all_docs))
        return len(all_docs)

    def _embed_batched(self, texts: list[str], batch_size: int) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = self._embedder.encode(batch, normalize_embeddings=True).tolist()
            all_embeddings.extend(vecs)
        return all_embeddings
