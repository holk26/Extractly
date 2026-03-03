from typing import List

from pydantic import BaseModel


class ExtractedPage(BaseModel):
    """Represents a single extracted page with its Markdown content."""

    url: str
    title: str
    content_markdown: str


class ExtractSiteResponse(BaseModel):
    """Response for the /api/extract-site endpoint."""

    start_url: str
    pages_extracted: int
    pages: List[ExtractedPage]
