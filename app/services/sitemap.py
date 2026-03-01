"""Sitemap-based URL discovery strategy."""

import logging
import re
from typing import List
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from app.services.fetcher import fetch_url

logger = logging.getLogger(__name__)

_SITEMAP_TIMEOUT = 15

# Query strings longer than this are assumed to belong to dynamic/archive pages
_MAX_QUERY_LENGTH = 50

# Common sitemap paths to probe in order
_SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
)

# Paths that indicate non-content pages (taxonomies, archives, admin, etc.)
_SKIP_PATTERN = re.compile(
    r"/(?:tag|tags|category|categories|author|authors|archive|archives|"
    r"feed|feeds|wp-content|wp-includes|wp-admin|wp-login|wp-json|"
    r"attachment|embed|page/\d+)(?:/|$)",
    re.IGNORECASE,
)


async def _fetch_text(url: str) -> str:
    """Return the response body of *url* as text, or an empty string on failure.

    Uses the SSRF-protected :func:`~app.services.fetcher.fetch_url` so that
    private/internal addresses are always rejected.
    """
    try:
        return await fetch_url(url)
    except (ValueError, httpx.HTTPError, RuntimeError):
        return ""


def _parse_sitemap(xml_text: str) -> List[str]:
    """Extract all ``<loc>`` values from a sitemap or sitemap-index XML."""
    urls: List[str] = []
    try:
        root = ElementTree.fromstring(xml_text)
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        for elem in root.iter(f"{ns}loc"):
            if elem.text:
                urls.append(elem.text.strip())
    except ElementTree.ParseError as exc:
        logger.warning("Failed to parse sitemap XML: %s", exc)
    return urls


def _is_content_url(url: str, base_netloc: str) -> bool:
    """Return *True* when *url* is likely a real content page on *base_netloc*."""
    parsed = urlparse(url)
    if parsed.netloc != base_netloc:
        return False
    if _SKIP_PATTERN.search(parsed.path):
        return False
    # Drop pages with very long query strings (dynamic/archive pages)
    if len(parsed.query) > _MAX_QUERY_LENGTH:
        return False
    return True


async def discover_urls_via_sitemap(base_url: str) -> List[str]:
    """Discover content-page URLs from the site's sitemap.

    Probes common sitemap paths, follows sitemap-index files recursively, and
    returns a deduplicated list of content-page URLs.

    Returns an empty list when no usable sitemap is found.
    """
    base_netloc = urlparse(base_url).netloc
    content_urls: List[str] = []
    seen_content: set = set()

    # Locate the first reachable sitemap
    initial_sitemap: str = ""
    for path in _SITEMAP_PATHS:
        candidate = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
        text = await _fetch_text(candidate)
        if text and ("<urlset" in text or "<sitemapindex" in text):
            initial_sitemap = candidate
            break

    if not initial_sitemap:
        return []

    # BFS over sitemap index → sub-sitemaps → content URLs
    sitemap_queue: List[str] = [initial_sitemap]
    processed_sitemaps: set = set()

    while sitemap_queue:
        sitemap_url = sitemap_queue.pop(0)
        if sitemap_url in processed_sitemaps:
            continue
        processed_sitemaps.add(sitemap_url)

        xml_text = await _fetch_text(sitemap_url)
        if not xml_text:
            continue

        for url in _parse_sitemap(xml_text):
            if url in seen_content:
                continue
            seen_content.add(url)

            parsed = urlparse(url)
            # Sub-sitemap: enqueue for processing
            if url.endswith(".xml") or "sitemap" in parsed.path.lower():
                sitemap_queue.append(url)
            elif _is_content_url(url, base_netloc):
                content_urls.append(url)

    return content_urls
