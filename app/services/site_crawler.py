"""Site-wide crawler that uses Playwright to extract all pages from a domain.

This module handles:
- Crawling all internal links from a base URL
- Using Playwright to render JavaScript-heavy pages
- Auto-scrolling to trigger lazy loading
- Converting each page to clean Markdown
"""

import ipaddress
import logging
import socket
from collections import deque
from typing import List, NamedTuple
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify
from playwright.async_api import async_playwright

from app.services.sanitizer import sanitize

logger = logging.getLogger(__name__)

# Hard ceiling to protect against runaway crawls
MAX_PAGES_HARD_LIMIT = 50
TIMEOUT_MS = 30_000  # 30 seconds
ALLOWED_SCHEMES = {"http", "https"}

# URL path prefixes to skip (common on WordPress and other CMSes)
_SKIP_PATH_PREFIXES = (
    "/wp-admin",
    "/wp-login",
    "/wp-json",
    "/wp-content",
)

_SKIP_PATH_SUFFIXES = (
    ".xml",
    ".rss",
    ".atom",
    "xmlrpc.php",
    "/feed",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".json",
)
_SKIP_PATH_SUFFIXES_STRIPPED = tuple(s.rstrip("/") for s in _SKIP_PATH_SUFFIXES)

# Query parameters that indicate non-content pages
_SKIP_QUERY_PARAMS = {"feed", "preview", "replytocom"}


class PageData(NamedTuple):
    """Extracted data from a single page."""

    url: str
    title: str
    content_markdown: str


def _is_private_address(hostname: str) -> bool:
    """Return True if hostname resolves to a private/loopback/link-local address."""
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
    """Raise ValueError if url fails SSRF / scheme validation."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' is not allowed. Use http or https.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname.")
    if _is_private_address(hostname):
        raise ValueError("Requests to private/internal addresses are not allowed.")


def _normalise(url: str) -> str:
    """Strip URL fragment so http://x.com/page#sec and http://x.com/page are the same."""
    return urlparse(url)._replace(fragment="").geturl()


def _same_domain(url: str, base_netloc: str) -> bool:
    """Return True when url belongs to base_netloc (exact host match)."""
    return urlparse(url).netloc == base_netloc


def _should_skip(url: str) -> bool:
    """Return True for URLs that are unlikely to contain useful page content."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    if any(path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
        return True
    path_stripped = path.rstrip("/")
    if any(path_stripped.endswith(suffix) for suffix in _SKIP_PATH_SUFFIXES_STRIPPED):
        return True

    # Skip if any noise query param is present
    query_params = set(parse_qs(parsed.query).keys())
    if query_params & _SKIP_QUERY_PARAMS:
        return True

    return False


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from HTML."""
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    return ""


def _extract_links(soup: BeautifulSoup, base_url: str, base_netloc: str) -> List[str]:
    """Extract all internal links from the page."""
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        abs_url = urljoin(base_url, href)
        normalised = _normalise(abs_url)

        if normalised in seen:
            continue

        if not _same_domain(normalised, base_netloc):
            continue

        parsed = urlparse(normalised)
        if parsed.scheme not in ALLOWED_SCHEMES:
            continue

        seen.add(normalised)
        links.append(normalised)

    return links


def _find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Return the most likely main-content element."""
    for selector in (
        "article",
        "main",
        '[role="main"]',
        ".entry-content",
        ".post-content",
        ".page-content",
        ".wp-block-post-content",
    ):
        node = soup.select_one(selector)
        if node:
            return node
    return soup.find("body") or soup


async def _fetch_with_browser(url: str) -> str:
    """Fetch URL with Playwright, auto-scrolling to trigger lazy loading."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)

            # Auto-scroll to trigger lazy loading
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;

                            if (totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)

            # Wait for network to be idle after scrolling
            await page.wait_for_load_state("networkidle")

            html = await page.content()
        finally:
            await context.close()
            await browser.close()

    return html


async def crawl_site(
    start_url: str,
    max_pages: int = 5,
) -> List[PageData]:
    """Crawl all internal pages of a site using Playwright.

    Args:
        start_url: The starting URL to crawl from
        max_pages: Maximum number of pages to crawl (capped at MAX_PAGES_HARD_LIMIT)

    Returns:
        List of PageData objects, one for each successfully crawled page

    Raises:
        ValueError: If the URL fails SSRF / scheme validation
        RuntimeError: If browser operations fail
    """
    _validate_url(start_url)
    max_pages = min(max_pages, MAX_PAGES_HARD_LIMIT)
    base_netloc = urlparse(start_url).netloc

    visited: set = set()
    queue: deque = deque([start_url])
    results: List[PageData] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        normalised = _normalise(url)

        if normalised in visited:
            continue
        visited.add(normalised)

        if _should_skip(normalised):
            logger.debug("Site crawler: skipping non-content URL %s", normalised)
            continue

        try:
            logger.info("Site crawler: fetching %s", normalised)
            html = await _fetch_with_browser(normalised)
        except Exception as exc:
            logger.warning("Site crawler: failed to fetch %s – %s", normalised, exc)
            continue

        # Parse HTML and extract title
        raw_soup = BeautifulSoup(html, "lxml")
        title = _extract_title(raw_soup)

        # Extract links for further crawling (before sanitization)
        links = _extract_links(raw_soup, normalised, base_netloc)

        # Sanitize and convert to markdown
        clean_soup = sanitize(html)
        main_node = _find_main_content(clean_soup)
        content_markdown = markdownify(str(main_node), heading_style="ATX").strip()

        results.append(
            PageData(
                url=normalised,
                title=title,
                content_markdown=content_markdown,
            )
        )

        # Add new links to queue
        for link in links:
            if link not in visited:
                queue.append(link)

    return results
