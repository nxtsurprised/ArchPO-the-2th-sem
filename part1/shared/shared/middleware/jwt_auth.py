from __future__ import annotations
from uuid import UUID
import structlog
from fastapi import Request, HTTPException, status

logger = structlog.get_logger()


class JWTAuth:
    """
    Middleware-зависимость для проверки JWT во всех сервисах кроме Auth.

    Схема работы:
      1. Читает заголовок Authorization: Bearer <token>.
      2. Загружает публичный ключ RS256 из Auth Service через JWKS-эндпоинт.
      3. Кешует ключ на 1 час, чтобы не ходить в Auth при каждом запросе.
      4. Верифицирует подпись и срок жизни токена (exp).
      5. Парсит payload в TokenPayload и кладёт его в request.state.user,
         откуда его потом читают роутеры через Depends(get_current_user).

    Асимметричная схема (RS256) важна: другие сервисы могут проверять токен,
    но не могут его выпустить – приватный ключ есть только у Auth Service.
    """

    def __init__(self, auth_service_url: str, cache):
        # Убираем trailing slash, чтобы не получить двойной слеш в URL
        self.auth_service_url = auth_service_url.rstrip("/")
        self.cache = cache
        self._jwks_uri = f"{self.auth_service_url}/.well-known/jwks.json"

    async def _get_public_key(self, token: str):
        """Возвращает подписывающий ключ из кеша или загружает его заново."""
        import jwt as pyjwt
        from jwt import PyJWKClient

        cache_key = "jwks:public_key"

        # Сначала проверяем кеш – типичный путь при нормальной работе
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Кеш холодный – делаем HTTP-запрос к Auth Service
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(self._jwks_uri)
            resp.raise_for_status()
            jwks_data = resp.json()

        # PyJWKClient умеет сопоставить kid из заголовка токена с ключом в JWKS
        jwks_client = PyJWKClient(self._jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Кешируем на 1 час (3600 секунд)
        await self.cache.set(cache_key, signing_key, ttl_seconds=3600)
        return signing_key

    async def __call__(self, request: Request):
        """
        Вызывается как FastAPI Dependency.
        При успехе возвращает TokenPayload и записывает его в request.state.user.
        При ошибке бросает HTTPException 401.
        """
        from shared.schemas.user import TokenPayload, ProjectRole

        # Проверяем наличие и формат заголовка
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Missing or invalid Authorization header"},
            )

        # Извлекаем сам токен – всё после "Bearer "
        token = auth_header.split(" ", 1)[1]

        try:
            import jwt as pyjwt
            signing_key = await self._get_public_key(token)
            # Декодируем и сразу проверяем подпись + exp + alg
            payload = pyjwt.decode(token, signing_key.key, algorithms=["RS256"])
        except Exception as e:
            logger.warning("jwt_verification_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
            )

        # Собираем список проектных ролей из payload
        roles = [
            ProjectRole(
                project_id=UUID(r["project_id"]),
                role=r["role"],
                side=r["side"],  # "customer" или "contractor"
            )
            for r in payload.get("roles", [])
        ]

        token_payload = TokenPayload(
            sub=UUID(payload["sub"]),           # ID пользователя
            org_id=UUID(payload["org_id"]),     # ID организации пользователя
            roles=roles,
            exp=payload["exp"],
            iat=payload["iat"],
            is_superadmin=payload.get("is_superadmin", False),
        )

        # Кладём результат в state запроса – роутеры читают его через get_current_user
        request.state.user = token_payload
        return token_payload
