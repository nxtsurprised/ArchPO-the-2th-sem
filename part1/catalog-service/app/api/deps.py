from __future__ import annotations
from uuid import UUID
import structlog
from fastapi import Request, HTTPException, status, Header

from app.config import get_settings
from shared.schemas.user import TokenPayload, ProjectRole

logger = structlog.get_logger()


async def _decode_token(token: str) -> dict:
    """Verify JWT using JWKS_URL (prod) or JWT_PUBLIC_KEY_PATH (dev/tests)."""
    import jwt as pyjwt

    settings = get_settings()

    if settings.JWT_PUBLIC_KEY_PATH:
        with open(settings.JWT_PUBLIC_KEY_PATH, "r") as fh:
            public_key = fh.read()
        return pyjwt.decode(token, public_key, algorithms=["RS256"])

    if settings.JWKS_URL:
        from jwt import PyJWKClient

        client = PyJWKClient(settings.JWKS_URL, cache_keys=True)
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

    token_payload = TokenPayload(
        sub=UUID(payload["sub"]),
        org_id=UUID(payload["org_id"]),
        roles=roles,
        exp=payload["exp"],
        iat=payload["iat"],
        is_superadmin=payload.get("is_superadmin", False),
    )
    request.state.user = token_payload
    return token_payload


def get_user_role_in_project(user: TokenPayload, project_id: str) -> str | None:
    """Return role name for project, None if user has no role there."""
    if user.is_superadmin:
        return "superadmin"
    for r in user.roles:
        if str(r.project_id) == project_id:
            return r.role
    return None


def require_project_role(allowed_roles: list[str], project_id: str, user: TokenPayload) -> None:
    """Raise 403 if user does not have one of the allowed roles in the project."""
    role = get_user_role_in_project(user, project_id)
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Insufficient permissions"},
        )


async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    if x_internal_secret != get_settings().INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Invalid internal secret"},
        )
