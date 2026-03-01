import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.request import ScrapeRequest
from app.models.response import ScrapeResponse
from app.services.browser_fetcher import fetch_url_with_browser
from app.services.detector import detect_platform
from app.services.extractor import extract
from app.services.fetcher import fetch_url

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse, summary="Scrape and clean a web page")
@limiter.limit("10/minute")
async def scrape(request: Request, body: ScrapeRequest) -> ScrapeResponse:
    """Fetch *url*, clean the HTML, and return structured Markdown content.

    The ``render_mode`` field controls how the page is fetched:

    * ``"auto"`` – Plain HTTP first; headless-browser fallback when a
      JavaScript SPA is detected (framework markers + thin content).
    * ``"http"`` – Plain HTTP only (fastest; may miss client-side content).
    * ``"browser"`` – Always use a headless Chromium browser (handles any SPA).
    """
    url = str(body.url)
    logger.info("Scrape request received", extra={"url": url, "render_mode": body.render_mode})

    # ── Step 1: fetch HTML ────────────────────────────────────────────────────
    if body.render_mode == "browser":
        html = await _fetch_with_browser(url)
    else:
        # "auto" or "http": always start with a plain HTTP request
        html = await _fetch_with_http(url)

    # ── Step 2: extract content and detect platform ───────────────────────────
    title, description, content_markdown, images, videos, links, word_count = extract(html, url)
    platform_type = detect_platform(html, word_count)

    # ── Step 3: SPA fallback (auto mode only) ─────────────────────────────────
    if body.render_mode == "auto" and platform_type == "spa":
        logger.info("SPA detected for %s – retrying with browser rendering", url)
        try:
            html = await _fetch_with_browser(url)
            title, description, content_markdown, images, videos, links, word_count = extract(
                html, url
            )
            platform_type = detect_platform(html, word_count)
        except Exception as exc:
            # Browser rendering failed; keep the HTTP result and the spa
            # platform_type so the caller knows what happened.
            logger.warning(
                "Browser rendering failed for %s (%s) – using HTTP result", url, exc
            )

    # ── Step 4: apply filters and return ─────────────────────────────────────
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
        platform_type=platform_type,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_with_http(url: str) -> str:
    """Fetch *url* via plain HTTP and propagate errors as HTTP exceptions."""
    try:
        return await fetch_url(url)
    except ValueError as exc:
        logger.warning("Invalid or blocked URL: %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.TimeoutException:
        logger.error("Timeout fetching URL: %s", url)
        raise HTTPException(status_code=504, detail="The target URL timed out.")
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error fetching URL %s: %s", url, exc)
        raise HTTPException(
            status_code=502, detail=f"Target URL returned HTTP {exc.response.status_code}."
        )
    except (httpx.RequestError, RuntimeError) as exc:
        logger.error("Error fetching URL %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))


async def _fetch_with_browser(url: str) -> str:
    """Fetch *url* with a headless browser and return the rendered HTML.

    Propagates errors as HTTP exceptions so the router can return a clean
    error response to the caller.
    """
    try:
        return await fetch_url_with_browser(url)
    except ValueError as exc:
        logger.warning("Invalid or blocked URL (browser): %s – %s", url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Browser rendering error for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected browser error for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail="Browser rendering failed.")


