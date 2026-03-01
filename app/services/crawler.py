"""Domain crawler: BFS-crawls all pages on the same domain as a seed URL."""

import logging
from collections import deque
from typing import List, NamedTuple
from urllib.parse import parse_qs, urlparse

import httpx

from app.services.extractor import extract
from app.services.fetcher import fetch_url

logger = logging.getLogger(__name__)

# Hard ceiling to protect against runaway crawls
MAX_PAGES_HARD_LIMIT = 50

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
)
# Pre-computed stripped versions to avoid repeated string operations at call time
_SKIP_PATH_SUFFIXES_STRIPPED = tuple(s.rstrip("/") for s in _SKIP_PATH_SUFFIXES)

# Query parameters that indicate non-content pages
_SKIP_QUERY_PARAMS = {"feed", "preview", "replytocom"}


class PageData(NamedTuple):
    url: str
    title: str
    description: str
    content_markdown: str
    images: List[str]
    videos: List[str]
    links: List[str]
    word_count: int


def _normalise(url: str) -> str:
    """Strip URL fragment so http://x.com/page#sec and http://x.com/page are the same."""
    return urlparse(url)._replace(fragment="").geturl()


def _same_domain(url: str, base_netloc: str) -> bool:
    """Return True when *url* belongs to *base_netloc* (exact host match)."""
    return urlparse(url).netloc == base_netloc


def _should_skip(url: str) -> bool:
    """Return True for URLs that are unlikely to contain useful page content.

    Skips WordPress admin/login/API paths, feed URLs, and static asset paths.
    """
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


async def crawl(
    start_url: str,
    max_pages: int = 10,
    max_depth: int = 3,
) -> List[PageData]:
    """Crawl pages on the same domain as *start_url* using BFS.

    The crawl is bounded by *max_pages* (total pages visited) and *max_depth*
    (link depth from the seed URL).  Both values are capped by
    ``MAX_PAGES_HARD_LIMIT`` / a depth ceiling of 5 to prevent abuse.

    WordPress admin, login, JSON API, feed, and preview URLs are automatically
    skipped to focus on content pages.

    Returns:
        A list of :class:`PageData` named-tuples, one per successfully fetched page.
    """
    max_pages = min(max_pages, MAX_PAGES_HARD_LIMIT)
    base_netloc = urlparse(start_url).netloc

    visited: set = set()
    # Queue entries: (url, depth)
    queue: deque = deque([(start_url, 0)])
    results: List[PageData] = []

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        normalised = _normalise(url)

        if normalised in visited:
            continue
        visited.add(normalised)

        if _should_skip(normalised):
            logger.debug("Crawler: skipping non-content URL %s", normalised)
            continue

        try:
            html = await fetch_url(normalised)
        except (ValueError, httpx.HTTPError, RuntimeError) as exc:
            logger.warning("Crawler: skipping %s – %s", normalised, exc)
            continue

        title, description, content_markdown, images, videos, links, word_count = extract(
            html, normalised
        )
        results.append(
            PageData(
                url=normalised,
                title=title,
                description=description,
                content_markdown=content_markdown,
                images=images,
                videos=videos,
                links=links,
                word_count=word_count,
            )
        )

        if depth < max_depth:
            for link in links:
                link_norm = _normalise(link)
                if link_norm not in visited and _same_domain(link_norm, base_netloc):
                    queue.append((link_norm, depth + 1))

    return results
