"""WordPress REST API extraction strategy."""

import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from app.models.page import PageModel
from app.services.fetcher import _validate_url
from app.services.normalizer import generate_slug, make_frontmatter
from app.services.sanitizer import sanitize

logger = logging.getLogger(__name__)

_WP_API_TIMEOUT = 15
_WP_PAGE_SIZE = 100
_WP_RESOURCES = ("posts", "pages")


async def is_wordpress(base_url: str) -> bool:
    """Return *True* when the site exposes the WordPress REST API namespace."""
    api_url = urljoin(base_url.rstrip("/") + "/", "wp-json/wp/v2/")
    try:
        _validate_url(api_url)
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(api_url)
            return resp.status_code == 200 and "namespace" in resp.text
    except (ValueError, httpx.HTTPError):
        return False


async def _fetch_wp_resource(base_url: str, resource: str, max_items: int) -> List[dict]:
    """Fetch all items of a WordPress REST resource type with automatic pagination."""
    results: List[dict] = []
    page = 1
    api_url = urljoin(base_url.rstrip("/") + "/", f"wp-json/wp/v2/{resource}")
    fields = "id,link,title,content,excerpt,slug"

    _validate_url(api_url)
    async with httpx.AsyncClient(timeout=_WP_API_TIMEOUT, follow_redirects=True) as client:
        while len(results) < max_items:
            try:
                resp = await client.get(
                    api_url,
                    params={"per_page": _WP_PAGE_SIZE, "page": page, "_fields": fields},
                )
                # 400 indicates that the requested page number is beyond the total
                # pages available (WordPress REST API convention).
                if resp.status_code == 400:
                    break
                resp.raise_for_status()
                items = resp.json()
                if not items:
                    break
                results.extend(items)
                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("WP API error fetching %s page %d: %s", resource, page, exc)
                break

    return results[:max_items]


def _item_to_page(item: dict, base_url: str) -> Optional[PageModel]:
    """Convert a single WordPress REST API item to a :class:`PageModel`."""
    try:
        url = item.get("link", "")
        if not url:
            return None

        title = item.get("title", {}).get("rendered", "").strip()
        raw_content = item.get("content", {}).get("rendered", "")
        raw_excerpt = item.get("excerpt", {}).get("rendered", "")

        description = BeautifulSoup(raw_excerpt, "lxml").get_text(strip=True) if raw_excerpt else ""

        clean_soup = sanitize(raw_content)
        content_text = clean_soup.get_text(separator=" ", strip=True)
        content_md = markdownify(str(clean_soup), heading_style="ATX").strip()

        # Collect images
        base_netloc = urlparse(base_url).netloc
        images: List[str] = []
        seen_imgs: set = set()
        for img in clean_soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                abs_url = urljoin(url, src)
                if abs_url not in seen_imgs:
                    seen_imgs.add(abs_url)
                    images.append(abs_url)

        # Collect internal links
        internal_links: List[str] = []
        seen_links: set = set()
        for a in clean_soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_href = urljoin(url, href)
            if urlparse(abs_href).netloc == base_netloc and abs_href not in seen_links:
                seen_links.add(abs_href)
                internal_links.append(abs_href)

        slug = item.get("slug") or generate_slug(url, title)
        frontmatter = make_frontmatter(title, description, url, slug)
        full_markdown = f"{frontmatter}\n\n{content_md}" if content_md else frontmatter

        return PageModel(
            url=url,
            slug=slug,
            title=title,
            meta_description=description,
            content=content_text,
            content_markdown=full_markdown,
            images=images,
            internal_links=internal_links,
            canonical=url,
        )
    except Exception as exc:
        logger.warning("Failed to convert WP item to PageModel: %s", exc)
        return None


async def extract_via_wordpress_api(base_url: str, max_pages: int = 100) -> List[PageModel]:
    """Extract all posts and pages from a WordPress site via its REST API."""
    pages: List[PageModel] = []
    seen_urls: set = set()

    for resource in _WP_RESOURCES:
        if len(pages) >= max_pages:
            break
        try:
            items = await _fetch_wp_resource(base_url, resource, max_pages - len(pages))
        except Exception as exc:
            logger.warning("WP API error for resource '%s': %s", resource, exc)
            continue

        for item in items:
            page = _item_to_page(item, base_url)
            if page and page.url not in seen_urls:
                seen_urls.add(page.url)
                pages.append(page)

    return pages
