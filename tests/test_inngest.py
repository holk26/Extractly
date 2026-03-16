"""Tests for PRODUCTION_MODE auth bypass and the V2 scrape endpoint.

Scenarios covered:
- PRODUCTION_MODE=false disables authentication (no token needed).
- PRODUCTION_MODE=true (default) keeps authentication enabled.
- POST /v2/scrape enqueues an Inngest event and returns 200 with a job ID.
- POST /v2/scrape without auth returns 401 when PRODUCTION_MODE is true.
- POST /v2/scrape when Inngest send fails returns 502.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import require_auth
from app.main import app

client = TestClient(app)

_SIMPLE_HTML = (
    "<html><body><main>"
    "<h1>Hello</h1><p>Content here for testing.</p>"
    "</main></body></html>"
)


# ---------------------------------------------------------------------------
# PRODUCTION_MODE auth bypass
# ---------------------------------------------------------------------------


class TestDevModeAuthBypass:
    """When PRODUCTION_MODE=false, authentication is skipped entirely."""

    def test_dev_mode_true_bypasses_auth(self):
        """With PRODUCTION_MODE=false, protected endpoints accept requests without a token."""
        with (
            patch("app.dependencies.auth._PRODUCTION_MODE", False),
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_SIMPLE_HTML)),
        ):
            resp = client.post(
                "/v1/scrape",
                json={"url": "https://example.com", "render_mode": "http"},
                # No Authorization header
            )

        assert resp.status_code == 200

    def test_dev_mode_false_requires_auth(self):
        """With PRODUCTION_MODE=true, protected endpoints reject requests without a token."""
        with patch("app.dependencies.auth._PRODUCTION_MODE", True):
            # Remove bypass override so real auth runs
            app.dependency_overrides.pop(require_auth, None)
            try:
                resp = client.post("/v1/scrape", json={"url": "https://example.com"})
            finally:
                app.dependency_overrides[require_auth] = lambda: None

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /v2/scrape
# ---------------------------------------------------------------------------


class TestScrapeV2:
    """Tests for the async (Inngest-backed) V2 scrape endpoint."""

    def test_scrape_v2_enqueues_job_and_returns_200(self):
        """POST /v2/scrape should enqueue an Inngest event and return status/event_id."""
        with patch(
            "app.routers.scrape_v2.inngest_client.send",
            new=AsyncMock(return_value=["evt_abc123"]),
        ):
            resp = client.post(
                "/v2/scrape",
                json={"url": "https://example.com"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["event_id"] == "evt_abc123"
        assert body["url"] == "https://example.com/"

    def test_scrape_v2_without_auth_returns_401(self):
        """POST /v2/scrape returns 401 when auth is required and no token is supplied."""
        with patch("app.dependencies.auth._PRODUCTION_MODE", True):
            app.dependency_overrides.pop(require_auth, None)
            try:
                resp = client.post("/v2/scrape", json={"url": "https://example.com"})
            finally:
                app.dependency_overrides[require_auth] = lambda: None

        assert resp.status_code == 401

    def test_scrape_v2_inngest_failure_returns_502(self):
        """POST /v2/scrape returns 502 when Inngest send fails."""
        with patch(
            "app.routers.scrape_v2.inngest_client.send",
            new=AsyncMock(side_effect=Exception("Inngest unavailable")),
        ):
            resp = client.post(
                "/v2/scrape",
                json={"url": "https://example.com"},
            )

        assert resp.status_code == 502
        assert "Failed to enqueue" in resp.json()["detail"]
