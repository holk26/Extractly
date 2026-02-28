from typing import Literal

from pydantic import BaseModel, HttpUrl, Field


class PlaygroundScrapeRequest(BaseModel):
    url: HttpUrl
    include_images: bool = True
    include_links: bool = True
    format: Literal["markdown"] = "markdown"
    wait_for_selector: str | None = Field(
        default=None,
        description="CSS selector to wait for before capturing the rendered HTML.",
        examples=["#app", ".content-loaded"],
    )
    wait_ms: int = Field(
        default=0,
        ge=0,
        le=10_000,
        description="Extra milliseconds to wait after the page loads (max 10 000).",
    )
