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


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_PAGESPEED_SUCCESS_BODY = {
    "lighthouseResult": {
        "categories": {
            "performance": {"score": 0.92},
        },
        "audits": {
            "first-contentful-paint": {
                "numericValue": 1200.5,
                "displayValue": "1.2 s",
            },
            "largest-contentful-paint": {
                "numericValue": 2300.0,
                "displayValue": "2.3 s",
            },
            "total-blocking-time": {
                "numericValue": 50.0,
                "displayValue": "50 ms",
            },
            "cumulative-layout-shift": {
                "numericValue": 0.05,
                "displayValue": "0.05",
            },
            "speed-index": {
                "numericValue": 1800.0,
                "displayValue": "1.8 s",
            },
            "interactive": {
                "numericValue": 3100.0,
                "displayValue": "3.1 s",
            },
        },
    }
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
        """Partial API response: missing audits are returned as null."""
        sparse_body = {
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.80}},
                "audits": {},
            }
        }
        with _patch_pagespeed(json_body=sparse_body):
            data = client.get("/performance", params={"url": "https://example.com"}).json()
        assert data["performance_score"] == pytest.approx(0.80)
        assert data["first_contentful_paint"] is None
        assert data["largest_contentful_paint"] is None


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
