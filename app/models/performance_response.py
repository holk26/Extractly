from typing import Literal, Optional

from pydantic import BaseModel


class PerformanceMetric(BaseModel):
    """A single Lighthouse audit metric with its numeric value and human-readable display."""

    value: float
    display_value: str


class PerformanceResponse(BaseModel):
    """Response model for the GET /performance endpoint."""

    url: str
    strategy: Literal["mobile", "desktop"]
    performance_score: Optional[float]
    """Lighthouse performance score in the range [0, 1] (e.g. 0.92 → 92%)."""
    seo_score: Optional[float]
    """Lighthouse SEO score in the range [0, 1]."""
    accessibility_score: Optional[float]
    """Lighthouse accessibility score in the range [0, 1]."""
    best_practices_score: Optional[float]
    """Lighthouse best-practices score in the range [0, 1]."""

    first_contentful_paint: Optional[PerformanceMetric]
    largest_contentful_paint: Optional[PerformanceMetric]
    total_blocking_time: Optional[PerformanceMetric]
    cumulative_layout_shift: Optional[PerformanceMetric]
    speed_index: Optional[PerformanceMetric]
    time_to_interactive: Optional[PerformanceMetric]
