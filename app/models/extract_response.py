from typing import List, Literal, Optional

from pydantic import BaseModel

from app.models.crawl_response import SiteGlobalContext
from app.models.page import PageModel


class ExtractResponse(BaseModel):
    site_url: str
    strategy: Literal["wordpress_api", "sitemap", "crawler"]
    pages_found: int
    pages: List[PageModel]
    total_word_count: int
    site_global_context: Optional[SiteGlobalContext] = None
