from typing import Literal

from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    url: HttpUrl
    include_images: bool = True
    include_links: bool = True
    format: Literal["markdown"] = "markdown"
