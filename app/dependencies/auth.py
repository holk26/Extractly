"""Authentication dependency for FastAPI endpoints.

Validates every request against PocketBase's auth-refresh endpoint.
All protected routes must declare ``Depends(require_auth)``.

Using ``HTTPBearer`` registers a ``bearerAuth`` security scheme in the
OpenAPI spec so Swagger UI displays the 🔒 "Authorize" button, letting
users paste their PocketBase JWT directly in the browser.

Flow:
    1. Extract the Bearer token from the ``Authorization`` header.
    2. Forward it to PocketBase ``POST /api/collections/users/auth-refresh``.
    3. PocketBase returns 200 → the token is valid; continue.
    4. PocketBase returns anything else → raise HTTP 401 Unauthorized.

Dev mode:
    When the ``DEV_MODE`` environment variable is set to ``"true"`` (case-
    insensitive), authentication is completely bypassed.  This is intended
    for local development only.  **Never** set ``DEV_MODE=true`` in production.
"""

import logging
import os

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "https://panel.db.app.moonsbow.com")
_AUTH_REFRESH_PATH = "/api/collections/users/auth-refresh"

# auto_error=False so we can return a clean 401 instead of FastAPI's default 403
_http_bearer = HTTPBearer(auto_error=False)

# When DEV_MODE=true the auth check is skipped entirely.
# Default is production mode (auth enabled).
_DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() == "true"


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> None:
    """Verify the Bearer token against PocketBase.

    When ``DEV_MODE=true`` is set in the environment, this function returns
    immediately without performing any token validation (useful for local
    development).

    Raises HTTP 401 when:
    - The ``Authorization: Bearer <token>`` header is absent or malformed.
    - PocketBase rejects the token (non-200 response).
    - The PocketBase request itself fails (network error, timeout, etc.).
    """
    if _DEV_MODE:
        logger.debug("DEV_MODE enabled – skipping authentication")
        return

    if credentials is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    authorization_header = f"Bearer {credentials.credentials}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{POCKETBASE_URL}{_AUTH_REFRESH_PATH}",
                headers={"Authorization": authorization_header},
                timeout=10.0,
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Unauthorized")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Auth check failed: %s", exc)
        raise HTTPException(status_code=401, detail="Unauthorized")
