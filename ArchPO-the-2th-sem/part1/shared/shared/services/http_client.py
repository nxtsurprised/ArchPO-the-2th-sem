from __future__ import annotations
import asyncio
import structlog
import httpx

logger = structlog.get_logger()

# Таймауты на уровне соединения и чтения – подобраны под внутреннюю сеть
_DEFAULT_CONNECT_TIMEOUT = 2.0   # секунды до установки TCP-соединения
_DEFAULT_READ_TIMEOUT = 5.0      # секунды ожидания ответа после отправки запроса

# Стратегия повторов: 2 попытки после первого отказа
_MAX_RETRIES = 2
_RETRY_DELAYS = [0.5, 1.0]       # задержки между попытками – 0.5 с, затем 1 с


class InternalHttpClient:
    """
    Обёртка над httpx.AsyncClient для межсервисных запросов.

    Возможности:
      - Фиксированные таймауты connect/read/write/pool.
      - Автоматический retry на ConnectError и TimeoutException.
        Логика: пробуем 3 раза (1 + 2 retry), задержка растёт: 0.5 с, 1 с.
      - Автоматическая передача X-Internal-Secret во все запросы.
        Nginx блокирует /internal/* снаружи, но этот заголовок – дополнительный рубеж.
      - Пробрасывание X-Request-ID для сквозной трассировки между сервисами.
      - Структурированное логирование каждого запроса и ответа.
    """

    def __init__(self, internal_secret: str = "", base_url: str = ""):
        self._internal_secret = internal_secret
        timeout = httpx.Timeout(
            connect=_DEFAULT_CONNECT_TIMEOUT,
            read=_DEFAULT_READ_TIMEOUT,
            write=5.0,
            pool=5.0,
        )
        # Один клиент на весь жизненный цикл сервиса – переиспользует пул соединений
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    def _build_headers(self, correlation_id: str | None = None) -> dict:
        """Собирает служебные заголовки для межсервисного запроса."""
        headers: dict[str, str] = {}
        if self._internal_secret:
            # Секрет проверяется Auth Service на /internal/* эндпоинтах
            headers["X-Internal-Secret"] = self._internal_secret
        if correlation_id:
            # Пробрасываем correlation_id, чтобы он был виден в логах вызываемого сервиса
            headers["X-Request-ID"] = correlation_id
        return headers

    async def request(
        self,
        method: str,
        url: str,
        *,
        correlation_id: str | None = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Выполняет HTTP-запрос с автоматическим retry.

        Повтор происходит только при сетевых ошибках (ConnectError, TimeoutException).
        Ошибки на уровне HTTP (4xx, 5xx) не повторяются – это ответственность caller'а.
        """
        # Объединяем служебные заголовки с теми, что передал вызывающий код
        headers = self._build_headers(correlation_id)
        existing_headers = kwargs.pop("headers", {})
        headers.update(existing_headers)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):  # 0, 1, 2
            try:
                logger.info("http_request", method=method, url=url, attempt=attempt)
                response = await self._client.request(method, url, headers=headers, **kwargs)
                logger.info("http_response", method=method, url=url, status_code=response.status_code)
                return response
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "http_retry", method=method, url=url,
                        attempt=attempt, delay=delay, error=str(exc),
                    )
                    await asyncio.sleep(delay)

        # Все попытки исчерпаны – пробрасываем последнее исключение
        raise last_exc  # type: ignore

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def aclose(self) -> None:
        """Закрывает пул соединений. Вызывать при завершении работы сервиса."""
        await self._client.aclose()
