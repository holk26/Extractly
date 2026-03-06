"""Health-check endpoint.

GET /health returns the status of every critical system:
- api:     always "ok" if this code is running
- browser: launches a headless Chromium instance and immediately closes it
           to verify Playwright and the browser binary are functional

HTTP 200 → all checks passed (status="ok")
HTTP 503 → one or more checks failed (status="degraded")
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

router = APIRouter()


async def _check_browser() -> tuple[str, str]:
    """Try to launch and close headless Chromium.

    Returns:
        ("browser", "ok") on success, ("browser", error_message) on failure.
    """
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            await browser.close()
        return "browser", "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check – browser failed: %s", exc)
        return "browser", str(exc)


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Returns the status of every critical system. "
        "HTTP 200 means all checks passed; HTTP 503 means at least one check failed."
    ),
    tags=["monitoring"],
)
async def health_check() -> JSONResponse:
    """Run all system checks and return a structured status report."""
    checks: dict[str, str] = {"api": "ok"}

    name, result = await _check_browser()
    checks[name] = result

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "ok" else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )
