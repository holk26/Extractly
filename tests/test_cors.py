"""Tests for CORS middleware configuration.

Verifies that the allowed moonsbow.com origins receive the correct
Access-Control-Allow-Origin header and that other origins are rejected.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


ALLOWED_ORIGINS = [
    "https://moonsbow.com",
    "https://www.moonsbow.com",
    "https://panel.app.moonsbow.com",
    "https://sub.moonsbow.com",
]

DISALLOWED_ORIGINS = [
    "https://evil.com",
    "https://notmoonsbow.com",
    "http://moonsbow.com",                    # HTTP (not HTTPS) must be rejected
    "https://moonsbow.com.evil.com",          # lookalike – must be rejected
    "https://fakemoonsbow.com",               # no dot before moonsbow – rejected
    "https://evil.sub.moonsbow.com.hack.io",  # trailing non-.com – rejected by $ anchor
]


class TestCORSAllowedOrigins:
    @pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
    def test_preflight_returns_origin_for_allowed(self, origin: str):
        """OPTIONS preflight for allowed origins echoes back the origin."""
        resp = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == origin

    @pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
    def test_simple_request_returns_origin_for_allowed(self, origin: str):
        """Simple GET for allowed origins returns Access-Control-Allow-Origin."""
        resp = client.get("/health", headers={"Origin": origin})
        assert resp.headers.get("access-control-allow-origin") == origin


class TestCORSDisallowedOrigins:
    @pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
    def test_preflight_does_not_echo_disallowed_origin(self, origin: str):
        """OPTIONS preflight for disallowed origins must NOT echo the origin back."""
        resp = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != origin

    @pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
    def test_simple_request_does_not_echo_disallowed_origin(self, origin: str):
        """Simple GET for disallowed origins must NOT return that origin in CORS header."""
        resp = client.get("/health", headers={"Origin": origin})
        assert resp.headers.get("access-control-allow-origin") != origin
