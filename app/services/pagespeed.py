"""PageSpeed Insights service.

Calls the Google PageSpeed Insights API v5 and extracts the key Lighthouse
metrics into a :class:`~app.models.performance_response.PerformanceResponse`.

The optional ``PAGESPEED_API_KEY`` environment variable is read at import time.
When not set the API is called without a key, which is allowed but subject to
stricter rate limits by Google.
"""

import logging
import os
from typing import Any, Literal, Optional

import httpx

from app.models.performance_response import PerformanceMetric, PerformanceResponse

logger = logging.getLogger(__name__)

_PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_TIMEOUT_S = 30.0
_API_KEY: Optional[str] = os.getenv("PAGESPEED_API_KEY") or None


def _extract_metric(audits: dict[str, Any], key: str) -> Optional[PerformanceMetric]:
    """Return a :class:`PerformanceMetric` for *key* from *audits*, or ``None``."""
    audit = audits.get(key)
    if not audit:
        return None
    numeric = audit.get("numericValue")
    display = audit.get("displayValue", "")
    if numeric is None:
        return None
    return PerformanceMetric(value=round(float(numeric), 2), display_value=str(display))


async def fetch_pagespeed(
    url: str,
    strategy: Literal["mobile", "desktop"],
) -> PerformanceResponse:
    """Query the PageSpeed Insights API and return structured performance data.

    Args:
        url: The page URL to analyse.
        strategy: ``"mobile"`` or ``"desktop"``.

    Returns:
        A :class:`PerformanceResponse` populated with Lighthouse metrics.

    Raises:
        httpx.TimeoutException: When the PageSpeed API does not respond in time.
        httpx.HTTPStatusError: When the PageSpeed API returns a 4xx/5xx status.
        httpx.RequestError: For any other network-level failure.
        ValueError: When *url* is empty or *strategy* is invalid.
    """
    if not url:
        raise ValueError("url must not be empty")

    params: dict[str, str] = {"url": url, "strategy": strategy}
    if _API_KEY:
        params["key"] = _API_KEY

    logger.info("PageSpeed request", extra={"url": url, "strategy": strategy})

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.get(_PAGESPEED_API_URL, params=params)
        response.raise_for_status()

    data = response.json()

    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    perf_score: Optional[float] = None
    raw_score = categories.get("performance", {}).get("score")
    if raw_score is not None:
        perf_score = round(float(raw_score), 4)

    return PerformanceResponse(
        url=url,
        strategy=strategy,
        performance_score=perf_score,
        first_contentful_paint=_extract_metric(audits, "first-contentful-paint"),
        largest_contentful_paint=_extract_metric(audits, "largest-contentful-paint"),
        total_blocking_time=_extract_metric(audits, "total-blocking-time"),
        cumulative_layout_shift=_extract_metric(audits, "cumulative-layout-shift"),
        speed_index=_extract_metric(audits, "speed-index"),
        time_to_interactive=_extract_metric(audits, "interactive"),
    )
