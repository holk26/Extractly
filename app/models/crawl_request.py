from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class CrawlRequest(BaseModel):
    url: HttpUrl
    include_images: bool = True
    include_links: bool = True
    format: Literal["markdown"] = "markdown"
    max_pages: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of pages to crawl (1–50).",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum link depth from the seed URL (1–5).",
    )
