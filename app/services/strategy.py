"""Auto-detection orchestration: selects the best extraction strategy."""

import logging
from typing import List, Literal, Tuple
from urllib.parse import urlparse

import httpx

from app.models.page import PageModel
from app.services.crawler import crawl
from app.services.extractor import extract
from app.services.fetcher import fetch_url
from app.services.normalizer import extract_canonical, generate_slug, make_frontmatter
from app.services.sitemap import discover_urls_via_sitemap
from app.services.wordpress import extract_via_wordpress_api, is_wordpress

logger = logging.getLogger(__name__)

Strategy = Literal["wordpress_api", "sitemap", "crawler"]

# Absolute ceiling – prevents abuse regardless of what the caller requests
MAX_PAGES_HARD_LIMIT = 100


def _build_page_model(
    url: str,
    title: str,
    description: str,
    content_markdown: str,
    images: List[str],
    internal_links: List[str],
    canonical: str | None,
) -> PageModel:
    """Assemble a :class:`PageModel` from extracted fields."""
    slug = generate_slug(url, title)
    frontmatter = make_frontmatter(title, description, url, slug, canonical)
    full_markdown = f"{frontmatter}\n\n{content_markdown}" if content_markdown else frontmatter
    return PageModel(
        url=url,
        slug=slug,
        title=title,
        meta_description=description,
        content=content_markdown,
        content_markdown=full_markdown,
        images=images,
        internal_links=internal_links,
        canonical=canonical,
    )


async def _extract_url_list(
    urls: List[str],
    include_images: bool,
    include_links: bool,
    max_pages: int,
) -> List[PageModel]:
    """Fetch and extract content from a list of URLs."""
    results: List[PageModel] = []
    seen: set = set()

    for url in urls:
        if len(results) >= max_pages:
            break
        if url in seen:
            continue
        seen.add(url)

        try:
            html = await fetch_url(url)
        except (ValueError, httpx.HTTPError, RuntimeError) as exc:
            logger.warning("Strategy: skipping %s – %s", url, exc)
            continue

        title, description, content_markdown, images, _videos, links, _wc = extract(html, url)
        canonical = extract_canonical(html, url)

        base_netloc = urlparse(url).netloc
        internal_links = (
            [lnk for lnk in links if urlparse(lnk).netloc == base_netloc]
            if include_links
            else []
        )
        img_list = images if include_images else []

        results.append(
            _build_page_model(url, title, description, content_markdown, img_list, internal_links, canonical)
        )

    return results


async def auto_extract(
    start_url: str,
    max_pages: int = 20,
    max_depth: int = 3,
    include_images: bool = True,
    include_links: bool = True,
) -> Tuple[Strategy, List[PageModel]]:
    """Detect the best extraction strategy and return all extracted pages.

    Detection order:
    1. WordPress REST API (if ``/wp-json/wp/v2/`` responds)
    2. Sitemap-based extraction (if a sitemap is discoverable)
    3. BFS crawler (fallback)

    Returns:
        A tuple of *(strategy_name, list_of_pages)*.
    """
    max_pages = min(max_pages, MAX_PAGES_HARD_LIMIT)

    # ── 1. WordPress REST API ─────────────────────────────────────────────────
    if await is_wordpress(start_url):
        logger.info("Strategy: WordPress API detected for %s", start_url)
        try:
            pages = await extract_via_wordpress_api(start_url, max_pages=max_pages)
            if pages:
                if not include_images:
                    pages = [p.model_copy(update={"images": []}) for p in pages]
                if not include_links:
                    pages = [p.model_copy(update={"internal_links": []}) for p in pages]
                return "wordpress_api", pages
        except Exception as exc:
            logger.warning("WordPress API extraction failed, falling back: %s", exc)

    # ── 2. Sitemap ────────────────────────────────────────────────────────────
    sitemap_urls = await discover_urls_via_sitemap(start_url)
    if sitemap_urls:
        logger.info(
            "Strategy: Sitemap found %d URLs for %s", len(sitemap_urls), start_url
        )
        pages = await _extract_url_list(
            sitemap_urls, include_images, include_links, max_pages
        )
        if pages:
            return "sitemap", pages

    # ── 3. BFS Crawler (fallback) ─────────────────────────────────────────────
    logger.info("Strategy: Falling back to crawler for %s", start_url)
    raw_results = await crawl(start_url, max_pages=max_pages, max_depth=max_depth)

    pages = []
    for raw in raw_results:
        pages.append(
            _build_page_model(
                url=raw.url,
                title=raw.title,
                description=raw.description,
                content_markdown=raw.content_markdown,
                images=raw.images if include_images else [],
                internal_links=raw.links if include_links else [],
                canonical=None,
            )
        )

    return "crawler", pages
