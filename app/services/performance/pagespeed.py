"""PageSpeed Insights service.

Calls the Google PageSpeed Insights API v5 and extracts the key Lighthouse
metrics into a :class:`~app.models.performance_response.PerformanceResponse`.

The optional ``PAGESPEED_API_KEY`` environment variable is read at import time.
When not set the API is called without a key, which is allowed but subject to
stricter rate limits by Google.
"""

import logging
import os
from typing import Any, List, Literal, Optional

import httpx

from app.models.performance_response import (
    AuditDetail,
    CrUXDistribution,
    CrUXMetric,
    FieldData,
    Opportunity,
    PerformanceMetric,
    PerformanceResponse,
    ResourceItem,
    ResourceSummary,
)

logger = logging.getLogger(__name__)

_PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_TIMEOUT_S = 30.0
_API_KEY: Optional[str] = os.getenv("PAGESPEED_API_KEY") or None

# Audit IDs already surfaced as top-level metric fields – skip in diagnostics.
_CORE_METRIC_IDS = frozenset(
    {
        "first-contentful-paint",
        "largest-contentful-paint",
        "total-blocking-time",
        "cumulative-layout-shift",
        "speed-index",
        "interactive",
        "resource-summary",  # extracted into resource_summary field
    }
)

# scoreDisplayMode values that carry no actionable data.
_SKIP_DISPLAY_MODES = frozenset({"notApplicable", "manual", "error"})

# Audits with a Lighthouse score at or above this threshold are considered
# passing and are excluded from the diagnostics list.
_PASSING_SCORE_THRESHOLD = 0.9


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


def _extract_field_data(loading_exp: dict[str, Any]) -> Optional[FieldData]:
    """Build a :class:`FieldData` from a ``loadingExperience`` / ``originLoadingExperience`` dict."""
    if not loading_exp:
        return None

    metrics = loading_exp.get("metrics") or {}

    def _crux_metric(key: str) -> Optional[CrUXMetric]:
        m = metrics.get(key)
        if not m:
            return None
        distributions: List[CrUXDistribution] = [
            CrUXDistribution(
                min=d.get("min"),
                max=d.get("max"),
                proportion=float(d.get("proportion", 0.0)),
            )
            for d in (m.get("distributions") or [])
        ]
        return CrUXMetric(
            percentile=m.get("percentile"),
            category=str(m.get("category", "")),
            distributions=distributions,
        )

    return FieldData(
        overall_category=loading_exp.get("overall_category"),
        first_contentful_paint=_crux_metric("FIRST_CONTENTFUL_PAINT_MS"),
        largest_contentful_paint=_crux_metric("LARGEST_CONTENTFUL_PAINT_MS"),
        first_input_delay=_crux_metric("FIRST_INPUT_DELAY_MS"),
        cumulative_layout_shift=_crux_metric("CUMULATIVE_LAYOUT_SHIFT_SCORE"),
        interaction_to_next_paint=_crux_metric("INTERACTION_TO_NEXT_PAINT"),
        experimental_time_to_first_byte=_crux_metric("EXPERIMENTAL_TIME_TO_FIRST_BYTE"),
    )


def _extract_opportunities(audits: dict[str, Any]) -> List[Opportunity]:
    """Return Lighthouse opportunity audits (potential time/byte savings)."""
    result: List[Opportunity] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict):
            continue
        details = audit.get("details") or {}
        if details.get("type") != "opportunity":
            continue
        score = audit.get("score")
        result.append(
            Opportunity(
                id=audit_id,
                title=audit.get("title", ""),
                description=audit.get("description", ""),
                score=round(float(score), 4) if score is not None else None,
                display_value=audit.get("displayValue") or None,
                savings_ms=details.get("overallSavingsMs"),
                savings_bytes=details.get("overallSavingsBytes"),
            )
        )
    return result


def _extract_diagnostics(audits: dict[str, Any]) -> List[AuditDetail]:
    """Return Lighthouse diagnostic and informational audits.

    Excludes:
    * Core metric audits already in top-level fields.
    * Opportunity audits (handled by :func:`_extract_opportunities`).
    * Audits whose ``scoreDisplayMode`` carries no actionable data.
    * Passing audits (score == 1.0) to keep the response concise.
    """
    # Build the set of opportunity audit IDs so we can exclude them.
    opportunity_ids = {
        audit_id
        for audit_id, audit in audits.items()
        if isinstance(audit, dict) and (audit.get("details") or {}).get("type") == "opportunity"
    }

    result: List[AuditDetail] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict):
            continue
        if audit_id in _CORE_METRIC_IDS or audit_id in opportunity_ids:
            continue
        score_display_mode = audit.get("scoreDisplayMode", "")
        if score_display_mode in _SKIP_DISPLAY_MODES:
            continue

        score = audit.get("score")
        # Include informative audits (score is None) and failing/borderline audits.
        if score_display_mode != "informative" and score is not None and score >= _PASSING_SCORE_THRESHOLD:
            continue

        numeric = audit.get("numericValue")
        result.append(
            AuditDetail(
                id=audit_id,
                title=audit.get("title", ""),
                description=audit.get("description", ""),
                score=round(float(score), 4) if score is not None else None,
                display_value=audit.get("displayValue") or None,
                numeric_value=round(float(numeric), 2) if numeric is not None else None,
            )
        )
    return result


def _extract_resource_summary(audits: dict[str, Any]) -> Optional[ResourceSummary]:
    """Extract the ``resource-summary`` Lighthouse audit into a :class:`ResourceSummary`."""
    audit = audits.get("resource-summary")
    if not audit:
        return None

    details = audit.get("details") or {}
    items_raw = details.get("items") or []

    total_count: Optional[int] = None
    total_size: Optional[int] = None
    items: List[ResourceItem] = []

    for item in items_raw:
        resource_type = item.get("resourceType", "")
        if resource_type == "total":
            total_count = item.get("count")
            total_size = item.get("size")
        else:
            items.append(
                ResourceItem(
                    resource_type=resource_type,
                    label=item.get("label", resource_type),
                    count=int(item.get("count", 0)),
                    size=int(item.get("size", 0)),
                )
            )

    return ResourceSummary(
        total_count=total_count,
        total_size=total_size,
        items=items,
    )


async def fetch_pagespeed(
    url: str,
    strategy: Literal["mobile", "desktop"],
) -> PerformanceResponse:
    """Query the PageSpeed Insights API and return structured performance data.

    Args:
        url: The page URL to analyse.
        strategy: ``"mobile"`` or ``"desktop"``.

    Returns:
        A :class:`PerformanceResponse` populated with Lighthouse metrics,
        opportunities, diagnostics, resource summary, and real-world CrUX
        field data.

    Raises:
        httpx.TimeoutException: When the PageSpeed API does not respond in time.
        httpx.HTTPStatusError: When the PageSpeed API returns a 4xx/5xx status.
        httpx.RequestError: For any other network-level failure.
        ValueError: When *url* is empty or *strategy* is invalid.
    """
    if not url:
        raise ValueError("url must not be empty")

    # The API only returns categories that are explicitly requested.
    # Without specifying all four, seo/accessibility/best-practices come back empty.
    params: list[tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
        ("category", "performance"),
        ("category", "seo"),
        ("category", "accessibility"),
        ("category", "best-practices"),
    ]
    if _API_KEY:
        params.append(("key", _API_KEY))

    logger.info("PageSpeed request", extra={"url": url, "strategy": strategy})

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        response = await client.get(_PAGESPEED_API_URL, params=params)
        response.raise_for_status()

    data = response.json()

    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    def _category_score(key: str) -> Optional[float]:
        raw = categories.get(key, {}).get("score")
        return round(float(raw), 4) if raw is not None else None

    return PerformanceResponse(
        url=url,
        strategy=strategy,
        # Lighthouse category scores
        performance_score=_category_score("performance"),
        seo_score=_category_score("seo"),
        accessibility_score=_category_score("accessibility"),
        best_practices_score=_category_score("best-practices"),
        # Core lab metrics
        first_contentful_paint=_extract_metric(audits, "first-contentful-paint"),
        largest_contentful_paint=_extract_metric(audits, "largest-contentful-paint"),
        total_blocking_time=_extract_metric(audits, "total-blocking-time"),
        cumulative_layout_shift=_extract_metric(audits, "cumulative-layout-shift"),
        speed_index=_extract_metric(audits, "speed-index"),
        time_to_interactive=_extract_metric(audits, "interactive"),
        # Extended fields
        opportunities=_extract_opportunities(audits),
        diagnostics=_extract_diagnostics(audits),
        resource_summary=_extract_resource_summary(audits),
        field_data=_extract_field_data(data.get("loadingExperience") or {}),
        origin_field_data=_extract_field_data(data.get("originLoadingExperience") or {}),
    )
