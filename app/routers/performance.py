"""Performance endpoint.

GET /performance
    ?url=<page_url>
    &strategy=mobile   (default)
    &strategy=desktop
"""

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import require_auth
from app.models.performance_response import PerformanceResponse
from app.services.pagespeed import fetch_pagespeed

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    summary="Page performance via Google PageSpeed Insights",
    description=(
        "Runs a Google Lighthouse audit on the given URL using the PageSpeed Insights API "
        "and returns the key metrics (performance score, FCP, LCP, TBT, CLS, SI, TTI).\n\n"
        "Use `?strategy=mobile` (default) for a mobile simulation or "
        "`?strategy=desktop` for a desktop simulation."
    ),
    tags=["performance"],
)
async def get_performance(
    url: str = Query(..., description="The page URL to audit."),
    strategy: Literal["mobile", "desktop"] = Query(
        default="mobile",
        description="Device strategy for the Lighthouse audit: 'mobile' or 'desktop'.",
    ),
) -> PerformanceResponse:
    """Return Lighthouse performance metrics for *url*."""
    logger.info("Performance request received", extra={"url": url, "strategy": strategy})

    try:
        return await fetch_pagespeed(url, strategy)
    except ValueError as exc:
        logger.warning("Invalid performance request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.TimeoutException:
        logger.error("PageSpeed API timeout for %s", url)
        raise HTTPException(status_code=504, detail="The PageSpeed API request timed out.")
    except httpx.HTTPStatusError as exc:
        logger.error("PageSpeed API HTTP error for %s: %s", url, exc)
        raise HTTPException(
            status_code=502,
            detail=f"PageSpeed API returned HTTP {exc.response.status_code}.",
        )
    except (httpx.RequestError, RuntimeError) as exc:
        logger.error("PageSpeed API request error for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=str(exc))
