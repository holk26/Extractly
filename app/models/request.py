from typing import Literal

from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    url: HttpUrl
    include_images: bool = True
    include_links: bool = True
    format: Literal["markdown"] = "markdown"
    render_mode: Literal["auto", "http", "browser"] = "auto"
    """Rendering strategy for the target URL.

    ``"auto"`` (default)
        Try a plain HTTP fetch first.  If the page is detected as a
        JavaScript SPA (very thin content + framework markers), automatically
        fall back to headless-browser rendering via Playwright.

    ``"http"``
        Always use the lightweight HTTP fetcher.  Fastest option; may return
        incomplete content for SPAs.

    ``"browser"``
        Always render with a headless Chromium browser.  Required for SPAs
        that do not return meaningful HTML over plain HTTP.  Slower than
        ``"http"`` but handles any client-side rendering framework.
    """
