"""Playwright-based fetcher for JavaScript-rendered (dynamic) web pages."""

import ipaddress
import socket
from urllib.parse import urlparse

from playwright.async_api import async_playwright

MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB
TIMEOUT_MS = 30_000  # 30 s in milliseconds
ALLOWED_SCHEMES = {"http", "https"}


def _is_private_address(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private/loopback/link-local address."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        raw_ip = info[4][0].split("%")[0]
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return True
    return False


def _validate_url(url: str) -> None:
    """Raise ValueError if *url* fails SSRF / scheme validation."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' is not allowed. Use http or https.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname.")
    if _is_private_address(hostname):
        raise ValueError("Requests to private/internal addresses are not allowed.")


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
    _validate_url(url)

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
            await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=TIMEOUT_MS)

            if wait_ms > 0:
                await page.wait_for_timeout(wait_ms)

            html = await page.content()
        finally:
            await context.close()
            await browser.close()

    if len(html.encode()) > MAX_CONTENT_SIZE:
        raise RuntimeError("Rendered HTML exceeds the maximum allowed size.")

    return html
