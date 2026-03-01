from typing import List

from pydantic import BaseModel


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
