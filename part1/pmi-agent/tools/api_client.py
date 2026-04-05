"""HTTP-клиент для обращений к микросервисам системы ГОСТ 34."""

import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = structlog.get_logger(__name__)


class APIClientTool:
    """
    Инструмент для прямых HTTP-запросов к сервисам ГОСТ 34.
    Используется агентом Исполнителем для API-проверок без браузера.
    """

    def __init__(self, jwt_token: str | None = None) -> None:
        self._token = jwt_token
        self._client = httpx.AsyncClient(
            timeout=10.0,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def get(self, url: str) -> dict:
        response = await self._client.get(url)
        return {"status": response.status_code, "body": response.json()}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def post(self, url: str, payload: dict) -> dict:
        response = await self._client.post(url, json=payload)
        return {"status": response.status_code, "body": response.json()}

    async def auth_login(self, email: str, password: str) -> str | None:
        """Авторизоваться в системе и вернуть JWT-токен."""
        url = f"{settings.auth_service_url}/api/v1/auth/login"
        result = await self.post(url, {"email": email, "password": password})
        if result["status"] == 200:
            token = result["body"].get("access_token")
            self._token = token
            self._client.headers["Authorization"] = f"Bearer {token}"
            logger.info("api_auth_success", email=email)
            return token
        logger.warning("api_auth_failed", email=email, status=result["status"])
        return None

    async def health_check_all(self) -> dict[str, bool]:
        """Проверить доступность всех сервисов."""
        services = {
            "auth": f"{settings.auth_service_url}/health",
            "catalog": f"{settings.catalog_service_url}/health",
            "generation": f"{settings.generation_service_url}/health",
            "workflow": f"{settings.workflow_service_url}/health",
        }
        results: dict[str, bool] = {}
        for name, url in services.items():
            try:
                resp = await self._client.get(url, timeout=3.0)
                results[name] = resp.status_code == 200
            except Exception:
                results[name] = False
        return results
