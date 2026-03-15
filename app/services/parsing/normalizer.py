"""Data normalisation utilities: slug generation, canonical extraction, frontmatter."""

import re
import unicodedata
from typing import Optional
from urllib.parse import urljoin, urlparse


def generate_slug(url: str, title: str = "") -> str:
    """Generate a clean URL slug from the URL path, falling back to the page title.

    The slug is lowercased, ASCII-only, and uses hyphens as separators.
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    # Remove file extension from path segment
    path = re.sub(r"\.[^/]+$", "", path)

    # Use the last non-empty path segment or the full (cleaned) path
    if path:
        slug_base = path.split("/")[-1] or path.replace("/", "-")
    elif title:
        slug_base = title
    else:
        slug_base = parsed.netloc

    # Normalise unicode, keep only ASCII
    slug = unicodedata.normalize("NFKD", slug_base)
    slug = slug.encode("ascii", "ignore").decode("ascii")

    # Lowercase and replace runs of non-alphanumeric chars with a single hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower())
    slug = slug.strip("-")

    return slug or "page"


def extract_canonical(html: str, base_url: str) -> Optional[str]:
    """Return the canonical URL declared in *html*, or *None* if absent."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    link_tag = soup.find("link", rel="canonical")
    if link_tag and link_tag.get("href"):
        return urljoin(base_url, str(link_tag["href"]))

    og_url = soup.find("meta", attrs={"property": "og:url"})
    if og_url and og_url.get("content"):
        return urljoin(base_url, str(og_url["content"]))

    return None


def make_frontmatter(
    title: str,
    description: str,
    url: str,
    slug: str,
    canonical: Optional[str] = None,
) -> str:
    """Return a YAML frontmatter block for use in Markdown files."""
    lines = [
        "---",
        f'title: "{_escape_yaml(title)}"',
        f'description: "{_escape_yaml(description)}"',
        f'url: "{url}"',
        f'slug: "{slug}"',
    ]
    if canonical and canonical != url:
        lines.append(f'canonical: "{canonical}"')
    lines.append("---")
    return "\n".join(lines)


def _escape_yaml(value: str) -> str:
    """Escape characters that would break inline double-quoted YAML strings."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
