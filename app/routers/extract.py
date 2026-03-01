"""Auto-extraction endpoint: detects the best strategy and extracts all site content."""

import io
import json
import logging
import zipfile
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.extract_request import ExtractRequest
from app.models.extract_response import ExtractResponse
from app.models.page import PageModel
from app.services.strategy import auto_extract

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Auto-extract all content from a website",
    description=(
        "Automatically detects the best extraction strategy "
        "(WordPress API → Sitemap → Crawler) and returns all site content "
        "structured and ready for migration.\n\n"
        "Pass `?format=zip` to download a compressed archive containing one "
        "Markdown file per page plus a JSON index."
    ),
)
@limiter.limit("3/minute")
async def extract_site(
    request: Request,
    body: ExtractRequest,
    format: str = Query(default="json", description="Output format: 'json' or 'zip'."),
) -> ExtractResponse | StreamingResponse:
    """Auto-extract all content from *url* using the best available strategy."""
    url = str(body.url)
    logger.info(
        "Extract request received",
        extra={"url": url, "max_pages": body.max_pages, "max_depth": body.max_depth},
    )

    try:
        strategy, pages = await auto_extract(
            url,
            max_pages=body.max_pages,
            max_depth=body.max_depth,
            include_images=body.include_images,
            include_links=body.include_links,
        )
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except (httpx.RequestError, RuntimeError) as exc:
        logger.error("Error extracting site %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    total_word_count = sum(len(p.content.split()) for p in pages)

    if format == "zip":
        return _build_zip_response(url, strategy, pages)

    return ExtractResponse(
        site_url=url,
        strategy=strategy,
        pages_found=len(pages),
        pages=pages,
        total_word_count=total_word_count,
    )


def _build_zip_response(site_url: str, strategy: str, pages: list[PageModel]) -> StreamingResponse:
    """Return a :class:`StreamingResponse` containing a ZIP archive.

    The archive holds:
    - ``index.json`` – metadata index listing all pages.
    - ``content/<slug>.md`` – one Markdown file per page.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        index = {
            "site_url": site_url,
            "strategy": strategy,
            "pages_found": len(pages),
            "pages": [{"slug": p.slug, "url": p.url, "title": p.title} for p in pages],
        }
        zf.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=2))

        for page in pages:
            zf.writestr(f"content/{page.slug}.md", page.content_markdown)

    buffer.seek(0)
    domain = urlparse(site_url).netloc.replace(".", "-")
    filename = f"{domain}-content.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
