"""Tests for the ``require_auth`` dependency.

These tests intentionally override the ``bypass_auth`` autouse fixture from
``conftest.py`` so that the real authentication logic is exercised.

Scenarios covered:
- Missing ``Authorization`` header → HTTP 401
- PocketBase rejects the token (non-200) → HTTP 401
- PocketBase is unreachable (network error) → HTTP 401
- Valid token (PocketBase returns 200) → request passes through (not 401)
- GET /health does NOT require auth → always accessible
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import require_auth
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_SIMPLE_HTML = (
    "<html><body><main>"
    "<h1>Hello</h1><p>Content here for testing.</p>"
    "</main></body></html>"
)


# ---------------------------------------------------------------------------
# Module-level fixture: restore real auth for all tests in this file
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_real_auth():
    """Remove the conftest bypass so real auth logic runs in these tests."""
    app.dependency_overrides.pop(require_auth, None)
    yield
    # Re-install bypass after each test to avoid side-effects on other modules
    app.dependency_overrides[require_auth] = lambda: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pb_response(status_code: int) -> AsyncMock:
    """Build a mock httpx.AsyncClient that returns *status_code* from PocketBase."""
    mock_response = MagicMock()
    mock_response.status_code = status_code

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# Missing Authorization header
# ---------------------------------------------------------------------------

class TestMissingAuthHeader:
    def test_scrape_without_auth_returns_401(self):
        """POST /scrape without Authorization header returns 401."""
        resp = client.post("/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_performance_without_auth_returns_401(self):
        """GET /performance without Authorization header returns 401."""
        resp = client.get("/performance", params={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_crawl_without_auth_returns_401(self):
        """POST /crawl without Authorization header returns 401."""
        resp = client.post("/crawl", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_extract_without_auth_returns_401(self):
        """POST /extract without Authorization header returns 401."""
        resp = client.post("/extract", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_extract_site_without_auth_returns_401(self):
        """POST /api/extract-site without Authorization header returns 401."""
        resp = client.post("/api/extract-site", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_playground_scrape_without_auth_returns_401(self):
        """POST /playground/scrape without Authorization header returns 401."""
        resp = client.post("/playground/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_root_without_auth_returns_401(self):
        """GET / without Authorization header returns 401."""
        resp = client.get("/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Invalid / rejected token
# ---------------------------------------------------------------------------

class TestInvalidToken:
    def test_pocketbase_401_returns_401(self):
        """When PocketBase rejects the token, our API returns 401."""
        with patch("app.dependencies.auth.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_pb_response(401)
            resp = client.get(
                "/performance",
                params={"url": "https://example.com"},
                headers={"Authorization": "invalid_token"},
            )
        assert resp.status_code == 401

    def test_pocketbase_403_returns_401(self):
        """A 403 from PocketBase also yields 401 from our API."""
        with patch("app.dependencies.auth.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_pb_response(403)
            resp = client.get(
                "/performance",
                params={"url": "https://example.com"},
                headers={"Authorization": "some_token"},
            )
        assert resp.status_code == 401

    def test_pocketbase_network_error_returns_401(self):
        """A network error reaching PocketBase yields 401."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.dependencies.auth.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client
            resp = client.get(
                "/performance",
                params={"url": "https://example.com"},
                headers={"Authorization": "some_token"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Valid token
# ---------------------------------------------------------------------------

class TestValidToken:
    def test_valid_token_passes_through_to_endpoint(self):
        """When PocketBase returns 200, the request reaches the endpoint (not 401)."""
        from app.models.performance_response import PerformanceResponse

        mock_perf = PerformanceResponse(url="https://example.com", strategy="mobile")

        with (
            patch("app.dependencies.auth.httpx.AsyncClient") as mock_cls,
            patch(
                "app.routers.performance.fetch_pagespeed",
                new=AsyncMock(return_value=mock_perf),
            ),
        ):
            mock_cls.return_value = _mock_pb_response(200)
            resp = client.get(
                "/performance",
                params={"url": "https://example.com"},
                headers={"Authorization": "valid_token"},
            )

        assert resp.status_code == 200

    def test_valid_token_scrape_passes_through(self):
        """Valid token allows POST /scrape to reach the handler."""
        with (
            patch("app.dependencies.auth.httpx.AsyncClient") as mock_cls,
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_SIMPLE_HTML)),
        ):
            mock_cls.return_value = _mock_pb_response(200)
            resp = client.post(
                "/scrape",
                json={"url": "https://example.com", "render_mode": "http"},
                headers={"Authorization": "valid_token"},
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Health endpoint – must NOT require auth
# ---------------------------------------------------------------------------

class TestHealthNoAuth:
    def test_health_is_accessible_without_auth(self):
        """GET /health must respond without an Authorization header."""
        with patch("app.routers.health.async_playwright") as mock_ap:
            mock_pw = MagicMock()
            mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
            mock_pw.__aexit__ = AsyncMock(return_value=False)
            mock_browser = AsyncMock()
            mock_browser.close = AsyncMock()
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_ap.return_value = mock_pw

            resp = client.get("/health")

        assert resp.status_code != 401

    def test_health_status_code_is_not_401(self):
        """GET /health never returns 401 regardless of auth headers."""
        with patch("app.routers.health.async_playwright") as mock_ap:
            mock_pw = MagicMock()
            mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
            mock_pw.__aexit__ = AsyncMock(return_value=False)
            mock_pw.chromium.launch = AsyncMock(side_effect=Exception("no browser"))
            mock_ap.return_value = mock_pw

            resp = client.get("/health")

        # Could be 503 (degraded) but must never be 401
        assert resp.status_code != 401
