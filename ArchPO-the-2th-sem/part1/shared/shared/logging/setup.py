"""
Настройка структурированного логирования через structlog.

Все сервисы вызывают configure_logging() один раз при старте в main.py.
После этого любой вызов structlog.get_logger().info("event", field=value)
автоматически выводит JSON-строку вида:
  {"timestamp": "...", "level": "info", "event": "...", "correlation_id": "...", "field": "value"}

Это JSON, потому что Promtail (агент сбора логов) парсит его и индексирует
поля как метки в Loki — это позволяет фильтровать логи по level, service,
correlation_id без grep'а по тексту.
"""
from __future__ import annotations
import logging
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            # merge_contextvars — ключевой процессор: достаёт correlation_id и другие
            # поля, привязанные через bind_contextvars() в middleware, и добавляет
            # их к каждой лог-записи автоматически. Именно так correlation_id попадает
            # в логи без явной передачи во все функции.
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),     # ISO 8601 timestamp
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,            # stack trace в JSON-поле
            structlog.processors.JSONRenderer(),             # финальный рендер в JSON
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        # cache_logger_on_first_use: structlog кэширует bound logger после первого вызова.
        # Это устраняет накладные расходы на повторный поиск процессоров при каждом логе.
        cache_logger_on_first_use=True,
    )

    # Перенаправляем стандартный logging (используется uvicorn, sqlalchemy, aiokafka)
    # в тот же формат через basicConfig
    logging.basicConfig(
        format="%(message)s",
        level=logging.getLevelName(log_level),
    )
