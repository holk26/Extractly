"""Playwright-based fetcher for JavaScript-rendered (dynamic) web pages."""

from playwright.async_api import async_playwright

from app.services.fetching.url_utils import (
    BROWSER_TIMEOUT_MS,
    MAX_CONTENT_SIZE,
    validate_url,
)


async def fetch_url_with_browser(
    url: str,
    *,
    wait_for_selector: str | None = None,
    wait_ms: int = 0,
) -> str:
    """Render *url* with a headless Chromium browser and return the full HTML.

    Args:
        url: The target URL (must be http/https and public).
        wait_for_selector: Optional CSS selector to wait for before capturing HTML.
        wait_ms: Extra milliseconds to wait after the page loads (0 = no extra wait).

    Raises:
        ValueError: if the URL fails SSRF / scheme validation.
        RuntimeError: if the rendered HTML exceeds MAX_CONTENT_SIZE.
        playwright.async_api.Error: on browser/network errors.
    """
    validate_url(url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                # --no-sandbox is required when running as root inside a container
                # (Docker drops the user namespace needed by Chromium's sandbox).
                # In non-containerised environments, omit this flag and rely on the
                # OS-level sandbox instead.
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=BROWSER_TIMEOUT_MS)

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=BROWSER_TIMEOUT_MS)

            if wait_ms > 0:
                await page.wait_for_timeout(wait_ms)

            html = await page.content()
        finally:
            await context.close()
            await browser.close()

    if len(html.encode()) > MAX_CONTENT_SIZE:
        raise RuntimeError("Rendered HTML exceeds the maximum allowed size.")

    return html
