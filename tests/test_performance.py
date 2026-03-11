"""Tests for the GET /performance endpoint.

All calls to the PageSpeed Insights API are replaced with lightweight mocks so
the suite runs without internet access or a real API key.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Maximum allowed deviation from 1.0 when validating that histogram bucket
# proportions sum to 100 %.
_PROPORTION_SUM_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_PAGESPEED_SUCCESS_BODY = {
    # ------------------------------------------------------------------
    # Real-world CrUX field data for the specific URL
    # ------------------------------------------------------------------
    "loadingExperience": {
        "id": "https://example.com/",
        "overall_category": "AVERAGE",
        "metrics": {
            "FIRST_CONTENTFUL_PAINT_MS": {
                "percentile": 1500,
                "category": "AVERAGE",
                "distributions": [
                    {"min": 0, "max": 1800, "proportion": 0.60},
                    {"min": 1800, "max": 3000, "proportion": 0.25},
                    {"min": 3000, "proportion": 0.15},
                ],
            },
            "LARGEST_CONTENTFUL_PAINT_MS": {
                "percentile": 2500,
                "category": "AVERAGE",
                "distributions": [
                    {"min": 0, "max": 2500, "proportion": 0.55},
                    {"min": 2500, "max": 4000, "proportion": 0.30},
                    {"min": 4000, "proportion": 0.15},
                ],
            },
            "FIRST_INPUT_DELAY_MS": {
                "percentile": 20,
                "category": "FAST",
                "distributions": [
                    {"min": 0, "max": 100, "proportion": 0.93},
                    {"min": 100, "max": 300, "proportion": 0.04},
                    {"min": 300, "proportion": 0.03},
                ],
            },
            "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                "percentile": 5,
                "category": "FAST",
                "distributions": [
                    {"min": 0, "max": 10, "proportion": 0.80},
                    {"min": 10, "max": 25, "proportion": 0.12},
                    {"min": 25, "proportion": 0.08},
                ],
            },
            "INTERACTION_TO_NEXT_PAINT": {
                "percentile": 140,
                "category": "AVERAGE",
                "distributions": [
                    {"min": 0, "max": 200, "proportion": 0.70},
                    {"min": 200, "max": 500, "proportion": 0.22},
                    {"min": 500, "proportion": 0.08},
                ],
            },
            "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {
                "percentile": 600,
                "category": "FAST",
                "distributions": [
                    {"min": 0, "max": 800, "proportion": 0.75},
                    {"min": 800, "max": 1800, "proportion": 0.18},
                    {"min": 1800, "proportion": 0.07},
                ],
            },
        },
    },
    # ------------------------------------------------------------------
    # Real-world CrUX field data for the entire origin
    # ------------------------------------------------------------------
    "originLoadingExperience": {
        "id": "https://example.com",
        "overall_category": "SLOW",
        "metrics": {
            "FIRST_CONTENTFUL_PAINT_MS": {
                "percentile": 2800,
                "category": "SLOW",
                "distributions": [
                    {"min": 0, "max": 1800, "proportion": 0.40},
                    {"min": 1800, "max": 3000, "proportion": 0.30},
                    {"min": 3000, "proportion": 0.30},
                ],
            },
        },
    },
    # ------------------------------------------------------------------
    # Lighthouse result
    # ------------------------------------------------------------------
    "lighthouseResult": {
        "categories": {
            "performance": {"score": 0.92},
            "seo": {"score": 0.98},
            "accessibility": {"score": 0.85},
            "best-practices": {"score": 0.75},
        },
        "audits": {
            # --- core lab metrics ---
            "first-contentful-paint": {
                "numericValue": 1200.5,
                "displayValue": "1.2 s",
                "scoreDisplayMode": "numeric",
                "score": 0.9,
            },
            "largest-contentful-paint": {
                "numericValue": 2300.0,
                "displayValue": "2.3 s",
                "scoreDisplayMode": "numeric",
                "score": 0.8,
            },
            "total-blocking-time": {
                "numericValue": 50.0,
                "displayValue": "50 ms",
                "scoreDisplayMode": "numeric",
                "score": 0.95,
            },
            "cumulative-layout-shift": {
                "numericValue": 0.05,
                "displayValue": "0.05",
                "scoreDisplayMode": "numeric",
                "score": 0.95,
            },
            "speed-index": {
                "numericValue": 1800.0,
                "displayValue": "1.8 s",
                "scoreDisplayMode": "numeric",
                "score": 0.9,
            },
            "interactive": {
                "numericValue": 3100.0,
                "displayValue": "3.1 s",
                "scoreDisplayMode": "numeric",
                "score": 0.85,
            },
            # --- opportunity audits ---
            "render-blocking-resources": {
                "id": "render-blocking-resources",
                "title": "Eliminate render-blocking resources",
                "description": "Resources are blocking the first paint of your page.",
                "score": 0.5,
                "scoreDisplayMode": "opportunity",
                "displayValue": "Potential savings of 450 ms",
                "details": {
                    "type": "opportunity",
                    "overallSavingsMs": 450.0,
                },
            },
            "unused-javascript": {
                "id": "unused-javascript",
                "title": "Remove unused JavaScript",
                "description": "Reduce unused JavaScript and defer loading scripts.",
                "score": 0.3,
                "scoreDisplayMode": "opportunity",
                "displayValue": "Potential savings of 120 KiB",
                "details": {
                    "type": "opportunity",
                    "overallSavingsMs": 800.0,
                    "overallSavingsBytes": 122880,
                },
            },
            # --- diagnostic audits ---
            "dom-size": {
                "id": "dom-size",
                "title": "Avoids an excessive DOM size",
                "description": "A large DOM will increase memory usage.",
                "score": 0.0,
                "scoreDisplayMode": "numeric",
                "numericValue": 1450,
                "displayValue": "1,450 elements",
            },
            "bootup-time": {
                "id": "bootup-time",
                "title": "Reduce JavaScript execution time",
                "description": "Consider reducing the time spent parsing, compiling, and executing JS.",
                "score": 0.5,
                "scoreDisplayMode": "numeric",
                "numericValue": 1200.0,
                "displayValue": "1.2 s",
            },
            "uses-long-cache-ttl": {
                "id": "uses-long-cache-ttl",
                "title": "Serve static assets with an efficient cache policy",
                "description": "A long cache lifetime can speed up repeat visits.",
                "score": 0.4,
                "scoreDisplayMode": "binary",
                "numericValue": 56789,
                "displayValue": "17 resources found",
            },
            "third-party-summary": {
                "id": "third-party-summary",
                "title": "Minimize third-party usage",
                "description": "Third-party code can significantly impact load performance.",
                "scoreDisplayMode": "informative",
                "score": None,
                "displayValue": "Third-party code blocked the main thread for 120 ms",
            },
            # --- passing audit (should NOT appear in diagnostics) ---
            "uses-http2": {
                "id": "uses-http2",
                "title": "Use HTTP/2",
                "description": "HTTP/2 offers many benefits over HTTP/1.1.",
                "score": 1.0,
                "scoreDisplayMode": "binary",
            },
            # --- notApplicable audit (should be excluded) ---
            "efficient-animated-content": {
                "id": "efficient-animated-content",
                "title": "Use video formats for animated content",
                "description": "Large GIFs are inefficient.",
                "score": None,
                "scoreDisplayMode": "notApplicable",
            },
            # --- resource summary ---
            "resource-summary": {
                "id": "resource-summary",
                "title": "Keep request counts low and transfer sizes small",
                "description": "To set budgets for the quantity and size of page resources.",
                "scoreDisplayMode": "informative",
                "score": None,
                "displayValue": "82 requests • 456 KiB",
                "details": {
                    "type": "table",
                    "items": [
                        {"resourceType": "total", "label": "Total", "count": 82, "size": 467456},
                        {"resourceType": "script", "label": "Script", "count": 15, "size": 234567},
                        {"resourceType": "image", "label": "Image", "count": 30, "size": 123456},
                        {"resourceType": "stylesheet", "label": "Stylesheet", "count": 5, "size": 45678},
                        {"resourceType": "other", "label": "Other", "count": 32, "size": 63755},
                    ],
                },
            },
        },
    },
}


def _make_mock_response(json_body: dict, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _patch_pagespeed(json_body: dict = _PAGESPEED_SUCCESS_BODY, status_code: int = 200):
    """Patch httpx.AsyncClient.get to return a fake PageSpeed API response."""
    mock_resp = _make_mock_response(json_body, status_code)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return patch("app.services.pagespeed.httpx.AsyncClient", return_value=mock_client)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestPerformanceSuccess:
    def test_returns_200(self):
        with _patch_pagespeed():
            resp = client.get("/performance", params={"url": "https://example.com"})
        assert resp.status_code == 200

    def test_response_contains_url_and_strategy(self):
        with _patch_pagespeed():
            data = client.get(
                "/performance",
                params={"url": "https://example.com", "strategy": "desktop"},
            ).json()
        assert data["url"] == "https://example.com"
        assert data["strategy"] == "desktop"

    def test_default_strategy_is_mobile(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["strategy"] == "mobile"

    def test_performance_score_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["performance_score"] == pytest.approx(0.92, abs=1e-4)

    def test_seo_score_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["seo_score"] == pytest.approx(0.98, abs=1e-4)

    def test_accessibility_score_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["accessibility_score"] == pytest.approx(0.85, abs=1e-4)

    def test_best_practices_score_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["best_practices_score"] == pytest.approx(0.75, abs=1e-4)

    def test_fcp_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["first_contentful_paint"]["display_value"] == "1.2 s"
        assert data["first_contentful_paint"]["value"] == pytest.approx(1200.5)

    def test_lcp_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["largest_contentful_paint"]["display_value"] == "2.3 s"

    def test_tbt_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["total_blocking_time"]["display_value"] == "50 ms"

    def test_cls_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["cumulative_layout_shift"]["display_value"] == "0.05"

    def test_speed_index_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["speed_index"]["display_value"] == "1.8 s"

    def test_tti_metric_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["time_to_interactive"]["display_value"] == "3.1 s"

    def test_missing_audits_return_none(self):
        """Partial API response: missing audits and category scores are returned as null."""
        sparse_body = {
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.80}},
                "audits": {},
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["performance_score"] == pytest.approx(0.80)
        assert data["seo_score"] is None
        assert data["accessibility_score"] is None
        assert data["best_practices_score"] is None
        assert data["first_contentful_paint"] is None
        assert data["largest_contentful_paint"] is None


# ---------------------------------------------------------------------------
# Opportunities (estimated savings)
# ---------------------------------------------------------------------------

class TestOpportunities:
    def test_opportunities_list_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert isinstance(data["opportunities"], list)

    def test_opportunity_ids_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [o["id"] for o in data["opportunities"]]
        assert "render-blocking-resources" in ids
        assert "unused-javascript" in ids

    def test_opportunity_has_required_fields(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        opp = next(o for o in data["opportunities"] if o["id"] == "render-blocking-resources")
        assert opp["title"] == "Eliminate render-blocking resources"
        assert "description" in opp
        assert opp["score"] == pytest.approx(0.5, abs=1e-4)
        assert opp["savings_ms"] == pytest.approx(450.0)

    def test_opportunity_byte_savings(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        opp = next(o for o in data["opportunities"] if o["id"] == "unused-javascript")
        assert opp["savings_bytes"] == pytest.approx(122880)
        assert opp["savings_ms"] == pytest.approx(800.0)

    def test_core_metrics_not_in_opportunities(self):
        """Audits already surfaced as top-level metrics must not appear in opportunities."""
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [o["id"] for o in data["opportunities"]]
        assert "first-contentful-paint" not in ids
        assert "largest-contentful-paint" not in ids

    def test_empty_opportunities_when_none_in_response(self):
        sparse_body = {
            "lighthouseResult": {
                "categories": {},
                "audits": {
                    "first-contentful-paint": {"numericValue": 1000.0, "displayValue": "1 s"},
                },
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["opportunities"] == []


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class TestDiagnostics:
    def test_diagnostics_list_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert isinstance(data["diagnostics"], list)

    def test_failing_numeric_audit_in_diagnostics(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "dom-size" in ids
        assert "bootup-time" in ids

    def test_informative_audit_in_diagnostics(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "third-party-summary" in ids

    def test_passing_audit_not_in_diagnostics(self):
        """An audit with score == 1.0 should be excluded from diagnostics."""
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "uses-http2" not in ids

    def test_not_applicable_audit_excluded(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "efficient-animated-content" not in ids

    def test_opportunity_audit_not_in_diagnostics(self):
        """Opportunity audits should not appear in the diagnostics list."""
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "render-blocking-resources" not in ids
        assert "unused-javascript" not in ids

    def test_resource_summary_not_in_diagnostics(self):
        """resource-summary is surfaced via resource_summary; not in diagnostics list."""
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        assert "resource-summary" not in ids

    def test_diagnostic_has_required_fields(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        diag = next(d for d in data["diagnostics"] if d["id"] == "dom-size")
        assert diag["title"] == "Avoids an excessive DOM size"
        assert "description" in diag
        assert diag["numeric_value"] == pytest.approx(1450.0)
        assert diag["display_value"] == "1,450 elements"

    def test_core_metrics_not_in_diagnostics(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ids = [d["id"] for d in data["diagnostics"]]
        for core_id in ("first-contentful-paint", "largest-contentful-paint",
                        "cumulative-layout-shift", "speed-index", "interactive"):
            assert core_id not in ids


# ---------------------------------------------------------------------------
# Resource summary
# ---------------------------------------------------------------------------

class TestResourceSummary:
    def test_resource_summary_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["resource_summary"] is not None

    def test_resource_summary_total_fields(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        rs = data["resource_summary"]
        assert rs["total_count"] == 82
        assert rs["total_size"] == 467456

    def test_resource_summary_items(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        items = data["resource_summary"]["items"]
        assert len(items) == 4  # total row excluded
        types = [i["resource_type"] for i in items]
        assert "script" in types
        assert "image" in types
        assert "stylesheet" in types
        assert "total" not in types

    def test_resource_item_fields(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        script_item = next(
            i for i in data["resource_summary"]["items"] if i["resource_type"] == "script"
        )
        assert script_item["count"] == 15
        assert script_item["size"] == 234567
        assert script_item["label"] == "Script"

    def test_resource_summary_null_when_absent(self):
        sparse_body = {
            "lighthouseResult": {
                "categories": {},
                "audits": {},
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["resource_summary"] is None


# ---------------------------------------------------------------------------
# Real-world field data (CrUX)
# ---------------------------------------------------------------------------

class TestFieldData:
    def test_field_data_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["field_data"] is not None

    def test_field_data_overall_category(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["field_data"]["overall_category"] == "AVERAGE"

    def test_field_data_fcp_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        fcp = data["field_data"]["first_contentful_paint"]
        assert fcp is not None
        assert fcp["percentile"] == 1500
        assert fcp["category"] == "AVERAGE"
        assert len(fcp["distributions"]) == 3

    def test_field_data_lcp_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        lcp = data["field_data"]["largest_contentful_paint"]
        assert lcp is not None
        assert lcp["category"] == "AVERAGE"

    def test_field_data_fid_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        fid = data["field_data"]["first_input_delay"]
        assert fid is not None
        assert fid["category"] == "FAST"

    def test_field_data_cls_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        cls_ = data["field_data"]["cumulative_layout_shift"]
        assert cls_ is not None
        assert cls_["category"] == "FAST"

    def test_field_data_inp_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        inp = data["field_data"]["interaction_to_next_paint"]
        assert inp is not None
        assert inp["percentile"] == 140
        assert inp["category"] == "AVERAGE"

    def test_field_data_ttfb_metric(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        ttfb = data["field_data"]["experimental_time_to_first_byte"]
        assert ttfb is not None
        assert ttfb["category"] == "FAST"

    def test_crux_distribution_structure(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        dist = data["field_data"]["first_contentful_paint"]["distributions"]
        assert all("proportion" in d for d in dist)
        proportions = [d["proportion"] for d in dist]
        assert abs(sum(proportions) - 1.0) < _PROPORTION_SUM_TOLERANCE

    def test_field_data_null_when_absent(self):
        sparse_body = {
            "lighthouseResult": {
                "categories": {},
                "audits": {},
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["field_data"] is None


# ---------------------------------------------------------------------------
# Origin field data (CrUX for entire origin)
# ---------------------------------------------------------------------------

class TestOriginFieldData:
    def test_origin_field_data_is_present(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["origin_field_data"] is not None

    def test_origin_field_data_overall_category(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["origin_field_data"]["overall_category"] == "SLOW"

    def test_origin_field_data_fcp(self):
        with _patch_pagespeed():
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        fcp = data["origin_field_data"]["first_contentful_paint"]
        assert fcp is not None
        assert fcp["percentile"] == 2800
        assert fcp["category"] == "SLOW"

    def test_origin_field_data_null_when_absent(self):
        sparse_body = {
            "lighthouseResult": {
                "categories": {},
                "audits": {},
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["origin_field_data"] is None


# ---------------------------------------------------------------------------
# Strategy validation
# ---------------------------------------------------------------------------

class TestPerformanceStrategyValidation:
    def test_mobile_strategy_accepted(self):
        with _patch_pagespeed():
            resp = client.get(
                "/performance", params={"url": "https://example.com", "strategy": "mobile"}
            )
        assert resp.status_code == 200

    def test_desktop_strategy_accepted(self):
        with _patch_pagespeed():
            resp = client.get(
                "/performance", params={"url": "https://example.com", "strategy": "desktop"}
            )
        assert resp.status_code == 200

    def test_invalid_strategy_returns_422(self):
        """FastAPI validates the Literal type; unsupported strategy → 422."""
        resp = client.get(
            "/performance", params={"url": "https://example.com", "strategy": "tablet"}
        )
        assert resp.status_code == 422

    def test_missing_url_returns_422(self):
        """URL is a required query parameter; omitting it → 422."""
        resp = client.get("/performance", params={"strategy": "mobile"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Error handling – upstream failures
# ---------------------------------------------------------------------------

class TestPerformanceErrorHandling:
    def test_pagespeed_timeout_returns_504(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("app.services.pagespeed.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/performance", params={"url": "https://example.com"})

        assert resp.status_code == 504

    def test_pagespeed_http_error_returns_502(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        exc = httpx.HTTPStatusError(
            "rate limited", request=MagicMock(), response=mock_response
        )
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=exc)

        with patch("app.services.pagespeed.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/performance", params={"url": "https://example.com"})

        assert resp.status_code == 502

    def test_pagespeed_request_error_returns_502(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError("connection refused")
        )

        with patch("app.services.pagespeed.httpx.AsyncClient", return_value=mock_client):
            resp = client.get("/performance", params={"url": "https://example.com"})

        assert resp.status_code == 502
