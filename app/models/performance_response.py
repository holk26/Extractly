from typing import List, Literal, Optional

from pydantic import BaseModel


class PerformanceMetric(BaseModel):
    """A single Lighthouse audit metric with its numeric value and human-readable display."""

    value: float
    display_value: str


# ---------------------------------------------------------------------------
# Chrome User Experience Report (CrUX / field data)
# ---------------------------------------------------------------------------


class CrUXDistribution(BaseModel):
    """A histogram bucket from the Chrome User Experience Report."""

    min: Optional[int] = None
    max: Optional[int] = None
    proportion: float


class CrUXMetric(BaseModel):
    """A single Chrome User Experience Report metric (real-world field data)."""

    percentile: Optional[float] = None
    """75th-percentile value for this metric in the field."""
    category: str
    """Classification of the metric: ``"FAST"``, ``"AVERAGE"``, or ``"SLOW"``."""
    distributions: List[CrUXDistribution] = []
    """Histogram showing the proportion of page loads in each bucket."""


class FieldData(BaseModel):
    """Real-world Core Web Vitals from the Chrome User Experience Report (CrUX).

    Present only when Google has collected sufficient field data for the URL or
    origin. Will be ``null`` when no data is available.
    """

    overall_category: Optional[str] = None
    """Overall experience category: ``"FAST"``, ``"AVERAGE"``, or ``"SLOW"``."""
    first_contentful_paint: Optional[CrUXMetric] = None
    largest_contentful_paint: Optional[CrUXMetric] = None
    first_input_delay: Optional[CrUXMetric] = None
    cumulative_layout_shift: Optional[CrUXMetric] = None
    interaction_to_next_paint: Optional[CrUXMetric] = None
    experimental_time_to_first_byte: Optional[CrUXMetric] = None


# ---------------------------------------------------------------------------
# Lighthouse opportunities (estimated savings)
# ---------------------------------------------------------------------------


class Opportunity(BaseModel):
    """A Lighthouse opportunity audit that suggests a concrete performance saving."""

    id: str
    """Lighthouse audit ID (e.g. ``"render-blocking-resources"``)."""
    title: str
    description: str
    score: Optional[float] = None
    """Lighthouse score in [0, 1]; lower means more potential savings."""
    display_value: Optional[str] = None
    savings_ms: Optional[float] = None
    """Estimated time savings in milliseconds."""
    savings_bytes: Optional[float] = None
    """Estimated byte savings."""


# ---------------------------------------------------------------------------
# Lighthouse diagnostics
# ---------------------------------------------------------------------------


class AuditDetail(BaseModel):
    """A Lighthouse diagnostic or informational audit result."""

    id: str
    """Lighthouse audit ID (e.g. ``"dom-size"``, ``"bootup-time"``)."""
    title: str
    description: str
    score: Optional[float] = None
    """Lighthouse score in [0, 1], or ``null`` for informative audits."""
    display_value: Optional[str] = None
    numeric_value: Optional[float] = None


# ---------------------------------------------------------------------------
# Resource summary
# ---------------------------------------------------------------------------


class ResourceItem(BaseModel):
    """Breakdown of a single resource type loaded by the page."""

    resource_type: str
    """Resource category (e.g. ``"script"``, ``"image"``, ``"stylesheet"``)."""
    label: str
    count: int
    """Number of requests of this type."""
    size: int
    """Total transfer size in bytes."""


class ResourceSummary(BaseModel):
    """Aggregate summary of all resources loaded by the page."""

    total_count: Optional[int] = None
    """Total number of network requests."""
    total_size: Optional[int] = None
    """Total transfer size in bytes."""
    items: List[ResourceItem] = []
    """Per-type breakdown (excludes the ``"total"`` row)."""


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class PerformanceResponse(BaseModel):
    """Response model for the GET /performance endpoint."""

    url: str
    strategy: Literal["mobile", "desktop"]

    # ------------------------------------------------------------------
    # Lighthouse category scores (0–1)
    # ------------------------------------------------------------------
    performance_score: Optional[float] = None
    """Lighthouse performance score in the range [0, 1] (e.g. 0.92 → 92%)."""
    seo_score: Optional[float] = None
    """Lighthouse SEO score in the range [0, 1]."""
    accessibility_score: Optional[float] = None
    """Lighthouse accessibility score in the range [0, 1]."""
    best_practices_score: Optional[float] = None
    """Lighthouse best-practices score in the range [0, 1]."""

    # ------------------------------------------------------------------
    # Core Lighthouse lab metrics
    # ------------------------------------------------------------------
    first_contentful_paint: Optional[PerformanceMetric] = None
    largest_contentful_paint: Optional[PerformanceMetric] = None
    total_blocking_time: Optional[PerformanceMetric] = None
    cumulative_layout_shift: Optional[PerformanceMetric] = None
    speed_index: Optional[PerformanceMetric] = None
    time_to_interactive: Optional[PerformanceMetric] = None

    # ------------------------------------------------------------------
    # Opportunities – estimated savings
    # ------------------------------------------------------------------
    opportunities: List[Opportunity] = []
    """Lighthouse opportunity audits with potential time/byte savings."""

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    diagnostics: List[AuditDetail] = []
    """Lighthouse diagnostic and informational audits highlighting issues."""

    # ------------------------------------------------------------------
    # Resource details
    # ------------------------------------------------------------------
    resource_summary: Optional[ResourceSummary] = None
    """Breakdown of all network resources loaded by the page."""

    # ------------------------------------------------------------------
    # Real-world field data (Chrome User Experience Report)
    # ------------------------------------------------------------------
    field_data: Optional[FieldData] = None
    """Real-world Core Web Vitals for this specific URL (CrUX data)."""
    origin_field_data: Optional[FieldData] = None
    """Real-world Core Web Vitals aggregated for the entire origin (CrUX data)."""
