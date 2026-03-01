from typing import List, Optional

from pydantic import BaseModel


class SiteGlobalContext(BaseModel):
    """Domain-level metadata aggregated across all crawled pages."""

    domain: str
    boilerplate_removed: bool


class PageResult(BaseModel):
    url: str
    title: str
    description: str
    content_markdown: str
    images: List[str]
    videos: List[str]
    links: List[str]
    word_count: int


class CrawlResponse(BaseModel):
    start_url: str
    pages_crawled: int
    pages: List[PageResult]
    total_word_count: int
    site_global_context: Optional[SiteGlobalContext] = None
