from pydantic import BaseModel, Field, HttpUrl


class ExtractRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of pages to extract (1–100).",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum crawl depth from the seed URL (1–5). Only used when falling back to the crawler strategy.",
    )
    include_images: bool = True
    include_links: bool = True
