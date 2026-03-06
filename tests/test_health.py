"""Tests for the /health endpoint.

These tests verify:
- 200 + status="ok" when all checks pass (browser launches successfully)
- 503 + status="degraded" when the browser check fails
- Response contains "api" and "browser" check keys
- No rate-limiting on the health endpoint
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_playwright_ok():
    """Return a mock async_playwright context where browser launch succeeds."""
    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()

    mock_pw = MagicMock()
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    return mock_pw


def _mock_playwright_fail(msg: str = "Chromium binary not found"):
    """Return a mock async_playwright context where browser launch raises."""
    mock_pw = MagicMock()
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)
    mock_pw.chromium.launch = AsyncMock(side_effect=Exception(msg))
    return mock_pw


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestHealthCheckOk:
    def test_returns_200_when_all_checks_pass(self):
        """Health endpoint returns HTTP 200 when browser launches successfully."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            resp = client.get("/health")

        assert resp.status_code == 200

    def test_status_is_ok_when_all_checks_pass(self):
        """Response body has status='ok' when all checks pass."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            data = client.get("/health").json()

        assert data["status"] == "ok"

    def test_api_check_always_ok(self):
        """The 'api' key is always 'ok' when the endpoint is reachable."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            data = client.get("/health").json()

        assert data["checks"]["api"] == "ok"

    def test_browser_check_ok_when_playwright_succeeds(self):
        """The 'browser' key is 'ok' when Playwright launches without error."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            data = client.get("/health").json()

        assert data["checks"]["browser"] == "ok"


# ---------------------------------------------------------------------------
# Degraded-path tests
# ---------------------------------------------------------------------------

class TestHealthCheckDegraded:
    def test_returns_503_when_browser_fails(self):
        """Health endpoint returns HTTP 503 when browser launch raises."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_fail()):
            resp = client.get("/health")

        assert resp.status_code == 503

    def test_status_is_degraded_when_browser_fails(self):
        """Response body has status='degraded' when browser check fails."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_fail()):
            data = client.get("/health").json()

        assert data["status"] == "degraded"

    def test_browser_check_contains_error_message(self):
        """The 'browser' key contains the error message on failure."""
        error_msg = "Chromium binary not found"
        with patch(
            "app.routers.health.async_playwright",
            return_value=_mock_playwright_fail(error_msg),
        ):
            data = client.get("/health").json()

        assert data["checks"]["browser"] == error_msg

    def test_api_check_still_ok_when_browser_fails(self):
        """The 'api' key remains 'ok' even when the browser check fails."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_fail()):
            data = client.get("/health").json()

        assert data["checks"]["api"] == "ok"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestHealthCheckSchema:
    def test_response_has_status_and_checks(self):
        """Response always contains top-level 'status' and 'checks' keys."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            data = client.get("/health").json()

        assert "status" in data
        assert "checks" in data

    def test_checks_contains_api_and_browser(self):
        """The 'checks' dict always contains both 'api' and 'browser' keys."""
        with patch("app.routers.health.async_playwright", return_value=_mock_playwright_ok()):
            data = client.get("/health").json()

        assert "api" in data["checks"]
        assert "browser" in data["checks"]
