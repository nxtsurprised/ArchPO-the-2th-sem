"""
Модель документа в MongoDB (Beanie ODM).

Документ — центральный объект: хранит заполненные данные секций, ссылки на
функции из справочника и метаданные о статусе согласования и архивировании.

Жизненный цикл статуса:
  draft → pending (отправлен на согласование) → approved / rejected / revision
  При revision документ возвращается в draft для доработки.

Поле locked управляется Kafka-consumer'ом (не API):
  workflow-service публикует document.locked / document.unlocked,
  catalog-service слушает топик и обновляет флаг в MongoDB.
  Это гарантирует, что блокировка работает даже при временной недоступности
  catalog — событие сохранится в Kafka и обработается при восстановлении.
"""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field
import uuid
from beanie import Document as BeanieDocument


class Document(BeanieDocument):
    # id задаётся как str UUID, а не ObjectId — для совместимости с остальными
    # сервисами, которые ожидают строковые идентификаторы в JSON.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    template_id: str | None = None
    name: str
    type: str | None = None  # tz | chtz | pmi | nmck
    status: Literal["draft", "pending", "approved", "revision", "rejected"] = "draft"
    # locked=True запрещает редактирование через API (409 DOCUMENT_LOCKED).
    # Устанавливается Kafka-consumer'ом при получении document.locked от workflow.
    locked: bool = False

    # function_ids — ссылки на записи в коллекции functions.
    # Хранятся как список ID, а не embedded-документы: функции переиспользуются
    # между документами одного проекта, и их обновление сразу отражается везде.
    function_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=lambda: {"sections": {}})

    version: int = 1   # инкрементируется при каждом update_document()
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    # ── Холодное хранилище ─────────────────────────────────────────────────────
    # Заполняется archive_service из generation-service после переноса файла в cold bucket.
    archived: bool = False
    archived_at: str | None = None   # ISO datetime когда был архивирован
    archive_key: str | None = None   # ключ объекта в MinIO documents-archive bucket

    class Settings:
        name = "documents"   # имя коллекции в MongoDB
