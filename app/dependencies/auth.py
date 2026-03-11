"""Authentication dependency for FastAPI endpoints.

Validates every request against PocketBase's auth-refresh endpoint.
All protected routes must declare ``Depends(require_auth)``.

Flow:
    1. Read the ``Authorization`` header from the incoming request.
    2. Forward it to PocketBase ``POST /api/collections/users/auth-refresh``.
    3. PocketBase returns 200 → the token is valid; continue.
    4. PocketBase returns anything else → raise HTTP 401 Unauthorized.
"""

import logging
import os

import httpx
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "https://panel.db.app.moonsbow.com")
_AUTH_REFRESH_PATH = "/api/collections/users/auth-refresh"


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Verify the ``Authorization`` token against PocketBase.

    Raises HTTP 401 when:
    - The ``Authorization`` header is absent.
    - PocketBase rejects the token (non-200 response).
    - The PocketBase request itself fails (network error, timeout, etc.).
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{POCKETBASE_URL}{_AUTH_REFRESH_PATH}",
                headers={"Authorization": authorization},
                timeout=10.0,
            )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Unauthorized")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Auth check failed: %s", exc)
        raise HTTPException(status_code=401, detail="Unauthorized")
