"""Domain crawler: BFS-crawls all pages on the same domain as a seed URL."""

import logging
from collections import deque
from typing import List, NamedTuple
from urllib.parse import urlparse

import httpx

from app.services.extractor import extract
from app.services.fetcher import fetch_url

logger = logging.getLogger(__name__)

# Hard ceiling to protect against runaway crawls
MAX_PAGES_HARD_LIMIT = 50


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


async def crawl(
    start_url: str,
    max_pages: int = 10,
    max_depth: int = 3,
) -> List[PageData]:
    """Crawl pages on the same domain as *start_url* using BFS.

    The crawl is bounded by *max_pages* (total pages visited) and *max_depth*
    (link depth from the seed URL).  Both values are capped by
    ``MAX_PAGES_HARD_LIMIT`` / a depth ceiling of 5 to prevent abuse.

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
