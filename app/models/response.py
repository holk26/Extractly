from typing import List

from pydantic import BaseModel


class ScrapeResponse(BaseModel):
    url: str
    title: str
    description: str
    content_markdown: str
    images: List[str]
    videos: List[str]
    links: List[str]
    word_count: int
    platform_type: str
    """Detected platform / rendering technology.

    One of ``"wordpress"``, ``"spa"``, ``"ssr"``, or ``"static"``.
    """
