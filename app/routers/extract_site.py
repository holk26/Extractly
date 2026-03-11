"""Router for the /api/extract-site endpoint.

This endpoint extracts all pages from a website (same domain) and converts
each page to clean Markdown.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies.auth import require_auth
from app.models.extract_site_request import ExtractSiteRequest
from app.models.extract_site_response import ExtractedPage, ExtractSiteResponse
from app.services.site_crawler import crawl_site

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


@router.post(
    "/extract-site",
    response_model=ExtractSiteResponse,
    summary="Extract entire website to Markdown",
    description=(
        "Crawls all internal pages (same domain) starting from the provided URL, "
        "using Playwright to render JavaScript content. Each page is converted to "
        "clean Markdown. Auto-scrolls each page to trigger lazy loading. "
        "Limited to max_pages (default 5, max 50) to prevent infinite loops."
    ),
)
@limiter.limit("3/minute")
async def extract_site_endpoint(request: Request, body: ExtractSiteRequest) -> ExtractSiteResponse:
    """Extract all pages from a site and convert to Markdown."""
    url = str(body.url)
    logger.info(
        "Extract-site request received",
        extra={"url": url, "max_pages": body.max_pages},
    )

    try:
        pages_data = await crawl_site(url, max_pages=body.max_pages)
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Error extracting site %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    pages = [
        ExtractedPage(
            url=page.url,
            title=page.title,
            content_markdown=page.content_markdown,
        )
        for page in pages_data
    ]

    return ExtractSiteResponse(
        start_url=url,
        pages_extracted=len(pages),
        pages=pages,
    )
