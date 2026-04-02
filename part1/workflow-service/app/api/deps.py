from __future__ import annotations
from uuid import UUID
from dataclasses import dataclass, field
import structlog
from fastapi import Request, HTTPException, status, Header

from app.config import get_settings

logger = structlog.get_logger()


@dataclass
class ProjectRole:
    project_id: UUID
    role: str
    side: str


@dataclass
class TokenPayload:
    sub: UUID
    org_id: UUID
    roles: list[ProjectRole] = field(default_factory=list)
    exp: int = 0
    iat: int = 0
    is_superadmin: bool = False


# Module-level JWKS client — created once, caches keys for 5 minutes
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        from jwt import PyJWKClient
        settings = get_settings()
        _jwks_client = PyJWKClient(settings.JWKS_URL, cache_jwk_set=True, lifespan=300)
    return _jwks_client


async def _decode_token(token: str) -> dict:
    import jwt as pyjwt

    settings = get_settings()

    if settings.JWT_PUBLIC_KEY_PATH:
        with open(settings.JWT_PUBLIC_KEY_PATH, "r") as fh:
            public_key = fh.read()
        return pyjwt.decode(token, public_key, algorithms=["RS256"])

    if settings.JWKS_URL:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        return pyjwt.decode(token, signing_key.key, algorithms=["RS256"])

    raise RuntimeError("Neither JWKS_URL nor JWT_PUBLIC_KEY_PATH is configured")


async def get_current_user(request: Request) -> TokenPayload:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid Authorization header"},
        )

    token = auth_header.split(" ", 1)[1]

    try:
        payload = await _decode_token(token)
    except Exception as exc:
        logger.warning("jwt_verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )

    roles = [
        ProjectRole(
            project_id=UUID(r["project_id"]),
            role=r["role"],
            side=r["side"],
        )
        for r in payload.get("roles", [])
    ]

    return TokenPayload(
        sub=UUID(payload["sub"]),
        org_id=UUID(payload["org_id"]),
        roles=roles,
        exp=payload["exp"],
        iat=payload["iat"],
        is_superadmin=payload.get("is_superadmin", False),
    )


def get_user_role_and_side(user: TokenPayload, project_id: str) -> tuple[str, str] | None:
    """Return (role, side) for the project, or None if user has no role there."""
    if user.is_superadmin:
        return ("superadmin", "customer")
    for r in user.roles:
        if str(r.project_id) == project_id:
            return (r.role, r.side)
    return None


def require_project_access(user: TokenPayload, project_id: str) -> tuple[str, str]:
    """Return (role, side) or raise 403."""
    result = get_user_role_and_side(user, project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "No access to this project"},
        )
    return result


async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    if x_internal_secret != get_settings().INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Invalid internal secret"},
        )
