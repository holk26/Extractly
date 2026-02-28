import logging

from fastapi import APIRouter, HTTPException, Request
from playwright.async_api import Error as PlaywrightError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.playground_request import PlaygroundScrapeRequest
from app.models.response import ScrapeResponse
from app.services.browser_fetcher import fetch_url_with_browser
from app.services.extractor import extract

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/playground", tags=["Playground"])


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    summary="Scrape a JavaScript-rendered page (Playground)",
    description=(
        "Renders the target URL in a headless Chromium browser so that "
        "JavaScript-heavy / Single-Page-Application (SPA) pages are fully "
        "executed before content extraction.  Accepts the same fields as "
        "`POST /scrape` plus optional `wait_for_selector` and `wait_ms` "
        "controls.\n\n"
        "**Note:** this endpoint is slower than `/scrape` because it spins up "
        "a real browser for each request."
    ),
)
@limiter.limit("5/minute")
async def playground_scrape(
    request: Request, body: PlaygroundScrapeRequest
) -> ScrapeResponse:
    url = str(body.url)
    logger.info(
        "Playground scrape request",
        extra={"url": url, "wait_for_selector": body.wait_for_selector, "wait_ms": body.wait_ms},
    )

    try:
        html = await fetch_url_with_browser(
            url,
            wait_for_selector=body.wait_for_selector,
            wait_ms=body.wait_ms,
        )
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Runtime error for URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except PlaywrightError as exc:
        logger.error("Browser error for URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=f"Browser error: {exc}")

    title, description, content_markdown, images, videos, links, word_count = extract(html, url)

    if not body.include_images:
        images = []
    if not body.include_links:
        links = []

    return ScrapeResponse(
        url=url,
        title=title,
        description=description,
        content_markdown=content_markdown,
        images=images,
        videos=videos,
        links=links,
        word_count=word_count,
    )
