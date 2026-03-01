from typing import List, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify

from app.services.cleaner import clean_markdown
from app.services.sanitizer import sanitize


def _normalize_url(base_url: str, href: str) -> str:
    """Return an absolute URL, resolving *href* against *base_url*."""
    return urljoin(base_url, href)


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return str(meta["content"]).strip()
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content"):
        return str(og_desc["content"]).strip()
    return ""


def _find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """Return the most likely main-content element.

    Checks common semantic selectors first, then WordPress-specific content
    containers, before falling back to <body>.
    """
    for selector in (
        "article",
        "main",
        '[role="main"]',
        # WordPress-specific content containers
        ".entry-content",
        ".post-content",
        ".page-content",
        ".wp-block-post-content",
    ):
        node = soup.select_one(selector)
        if node:
            return node
    # Fall back to <body> or the whole tree
    return soup.find("body") or soup


def _extract_images(node, base_url: str) -> List[str]:
    seen: set = set()
    images: List[str] = []
    for img in node.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src:
            abs_url = _normalize_url(base_url, src)
            if abs_url not in seen:
                seen.add(abs_url)
                images.append(abs_url)
    return images


def _extract_videos(node, base_url: str) -> List[str]:
    seen: set = set()
    videos: List[str] = []
    for video in node.find_all("video"):
        src = video.get("src")
        if src:
            abs_url = _normalize_url(base_url, src)
            if abs_url not in seen:
                seen.add(abs_url)
                videos.append(abs_url)
        for source in video.find_all("source"):
            src = source.get("src")
            if src:
                abs_url = _normalize_url(base_url, src)
                if abs_url not in seen:
                    seen.add(abs_url)
                    videos.append(abs_url)
    return videos


def _extract_links(node, base_url: str) -> List[str]:
    seen: set = set()
    links: List[str] = []
    base_host = urlparse(base_url).netloc
    for a in node.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        abs_url = _normalize_url(base_url, href)
        parsed = urlparse(abs_url)
        # Keep only http/https links that belong to the same host or are absolute
        if parsed.scheme not in ("http", "https"):
            continue
        if abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)
    return links


def extract(html: str, base_url: str) -> Tuple[str, str, str, List[str], List[str], List[str], int]:
    """Extract structured content from *html*.

    Returns:
        (title, description, content_markdown, images, videos, links, word_count)
    """
    # We need metadata (title, description) from the unsanitized soup first
    raw_soup = BeautifulSoup(html, "lxml")
    title = _extract_title(raw_soup)
    description = _extract_description(raw_soup)

    # Now sanitize and work on the clean tree
    clean_soup = sanitize(html)
    main_node = _find_main_content(clean_soup)

    images = _extract_images(main_node, base_url)
    videos = _extract_videos(main_node, base_url)
    links = _extract_links(main_node, base_url)

    content_markdown = clean_markdown(
        markdownify(str(main_node), heading_style="ATX").strip()
    )
    word_count = len(content_markdown.split())

    return title, description, content_markdown, images, videos, links, word_count
