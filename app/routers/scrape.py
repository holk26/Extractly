import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.request import ScrapeRequest
from app.models.response import ScrapeResponse
from app.services.extractor import extract
from app.services.fetcher import fetch_url

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse, summary="Scrape and clean a web page")
@limiter.limit("10/minute")
async def scrape(request: Request, body: ScrapeRequest) -> ScrapeResponse:
    """Fetch *url*, clean the HTML, and return structured Markdown content."""
    url = str(body.url)
    logger.info("Scrape request received", extra={"url": url})

    try:
        html = await fetch_url(url)
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.TimeoutException:
        logger.error("Timeout fetching URL: %s", url)
        raise HTTPException(status_code=504, detail="The target URL timed out.")
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error fetching URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=f"Target URL returned HTTP {exc.response.status_code}.")
    except (httpx.RequestError, RuntimeError) as exc:
        logger.error("Error fetching URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))

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
