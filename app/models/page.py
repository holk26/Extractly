from typing import List, Optional

from pydantic import BaseModel


class PageModel(BaseModel):
    """Unified internal model representing one extracted page."""

    url: str
    slug: str
    title: str
    meta_description: str
    content: str  # body content (markdown, without frontmatter)
    content_markdown: str  # full Markdown file ready for static-site use (frontmatter + body)
    images: List[str]
    internal_links: List[str]
    canonical: Optional[str] = None
