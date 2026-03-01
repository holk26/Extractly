import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.crawl_request import CrawlRequest
from app.models.crawl_response import CrawlResponse, PageResult, SiteGlobalContext
from app.services.crawler import PageData, crawl
from app.services.deduplicator import remove_boilerplate

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post(
    "/crawl",
    response_model=CrawlResponse,
    summary="Crawl and extract all pages of a domain",
    description=(
        "Starting from *url*, follows internal links (same hostname) up to "
        "`max_depth` levels deep and fetches up to `max_pages` pages.  "
        "Returns structured Markdown content for every successfully crawled page "
        "together with an aggregated word-count."
    ),
)
@limiter.limit("5/minute")
async def crawl_endpoint(request: Request, body: CrawlRequest) -> CrawlResponse:
    """BFS-crawl all same-domain pages reachable from *url*."""
    url = str(body.url)
    logger.info(
        "Crawl request received",
        extra={"url": url, "max_pages": body.max_pages, "max_depth": body.max_depth},
    )

    try:
        raw_results = await crawl(url, max_pages=body.max_pages, max_depth=body.max_depth)
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except (httpx.RequestError, RuntimeError) as exc:
        logger.error("Error crawling URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    pages = []
    total_word_count = 0

    # Apply cross-page boilerplate deduplication when multiple pages were crawled
    contents = [p.content_markdown for p in raw_results]
    deduped_contents, boilerplate_removed = remove_boilerplate(contents)

    for page, clean_content in zip(raw_results, deduped_contents):
        wc = len(clean_content.split())
        pages.append(
            PageResult(
                url=page.url,
                title=page.title,
                description=page.description,
                content_markdown=clean_content,
                images=page.images if body.include_images else [],
                videos=page.videos,
                links=page.links if body.include_links else [],
                word_count=wc,
            )
        )
        total_word_count += wc

    domain = urlparse(url).netloc
    site_ctx = SiteGlobalContext(domain=domain, boilerplate_removed=boilerplate_removed)

    return CrawlResponse(
        start_url=url,
        pages_crawled=len(pages),
        pages=pages,
        total_word_count=total_word_count,
        site_global_context=site_ctx,
    )
