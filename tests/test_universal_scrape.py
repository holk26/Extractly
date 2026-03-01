"""Tests for the universal /scrape endpoint.

These tests exercise the full scrape router including:
- render_mode selection (auto / http / browser)
- platform_type in the response
- SPA auto-detection and browser fallback
- WordPress detection via HTML markers
- Error propagation

All external network calls and the Playwright browser are replaced with
lightweight mocks so the tests run without internet access.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear the slowapi in-memory counter before every test."""
    app.state.limiter._storage.reset()
    yield

# ---------------------------------------------------------------------------
# Shared HTML fixtures
# ---------------------------------------------------------------------------

_STATIC_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Static Site Page</title>
  <meta name="description" content="A plain static page.">
</head>
<body>
  <main>
    <h1>Hello World</h1>
    <p>This is a fully server-rendered page with plenty of readable content
    that satisfies the word-count threshold for SSR detection.</p>
    <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua.</p>
  </main>
</body>
</html>
"""

_WP_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>My WordPress Blog</title>
  <link rel="https://api.w.org/" href="https://example.com/wp-json/">
</head>
<body>
  <div class="entry-content">
    <h1>Hello from WordPress</h1>
    <p>WordPress-powered content goes here.</p>
  </div>
</body>
</html>
"""

_SPA_SHELL_HTML = """
<!DOCTYPE html>
<html>
<head><title>React App</title></head>
<body>
  <div id="root"></div>
  <script src="/static/js/main.js"></script>
</body>
</html>
"""

_SPA_RENDERED_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>React App</title>
  <meta name="description" content="Rendered by the browser.">
</head>
<body>
  <div id="root">
    <main>
      <h1>Welcome to the SPA</h1>
      <p>This content was produced by client-side JavaScript rendering and
      contains enough words to satisfy the extraction threshold.</p>
    </main>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(url: str = "https://example.com", **kwargs):
    """POST to /scrape with sensible defaults."""
    payload = {"url": url, **kwargs}
    return client.post("/scrape", json=payload)


# ---------------------------------------------------------------------------
# render_mode=http  –  plain HTTP, no browser
# ---------------------------------------------------------------------------

class TestScrapeHttpMode:
    def test_http_mode_ssr_page(self):
        with patch(
            "app.routers.scrape.fetch_url", new=AsyncMock(return_value=_STATIC_HTML)
        ):
            resp = _post(render_mode="http")

        assert resp.status_code == 200
        data = resp.json()
        assert data["platform_type"] == "ssr"
        assert "Hello World" in data["content_markdown"]
        assert data["word_count"] > 0

    def test_http_mode_wordpress_page(self):
        with patch(
            "app.routers.scrape.fetch_url", new=AsyncMock(return_value=_WP_HTML)
        ):
            resp = _post(render_mode="http")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "wordpress"

    def test_http_mode_does_not_trigger_browser_for_spa(self):
        """render_mode=http must never invoke the browser even for SPAs."""
        with (
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_SPA_SHELL_HTML)),
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(side_effect=AssertionError("browser must not be called")),
            ),
        ):
            resp = _post(render_mode="http")

        assert resp.status_code == 200
        # SPA shell was fetched over HTTP; platform is spa but browser was NOT used
        assert resp.json()["platform_type"] == "spa"


# ---------------------------------------------------------------------------
# render_mode=auto  –  HTTP first, browser fallback for SPAs
# ---------------------------------------------------------------------------

class TestScrapeAutoMode:
    def test_auto_mode_ssr_page_no_browser(self):
        """SSR pages must not trigger browser rendering in auto mode."""
        with (
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_STATIC_HTML)),
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(side_effect=AssertionError("browser must not be called")),
            ),
        ):
            resp = _post(render_mode="auto")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "ssr"

    def test_auto_mode_spa_triggers_browser_fallback(self):
        """SPA detected in auto mode → browser is called and rendered content returned."""
        with (
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_SPA_SHELL_HTML)),
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(return_value=_SPA_RENDERED_HTML),
            ),
        ):
            resp = _post(render_mode="auto")

        assert resp.status_code == 200
        data = resp.json()
        # After browser rendering the content is rich
        assert "Welcome to the SPA" in data["content_markdown"]
        assert data["word_count"] > 0

    def test_auto_mode_spa_browser_failure_falls_back_to_http_result(self):
        """If browser fails in auto mode, return the HTTP-fetched result."""
        with (
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_SPA_SHELL_HTML)),
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(side_effect=RuntimeError("browser crashed")),
            ),
        ):
            resp = _post(render_mode="auto")

        # Still 200 – HTTP result is returned as fallback
        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "spa"

    def test_auto_mode_wordpress_page(self):
        """WordPress pages in auto mode are served via HTTP (WP API is separate)."""
        with (
            patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_WP_HTML)),
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(side_effect=AssertionError("browser must not be called")),
            ),
        ):
            resp = _post(render_mode="auto")

        assert resp.status_code == 200
        assert resp.json()["platform_type"] == "wordpress"


# ---------------------------------------------------------------------------
# render_mode=browser  –  always use headless browser
# ---------------------------------------------------------------------------

class TestScrapeBrowserMode:
    def test_browser_mode_uses_browser_fetcher(self):
        with (
            patch(
                "app.routers.scrape.fetch_url_with_browser",
                new=AsyncMock(return_value=_SPA_RENDERED_HTML),
            ),
            patch(
                "app.routers.scrape.fetch_url",
                new=AsyncMock(side_effect=AssertionError("http must not be called")),
            ),
        ):
            resp = _post(render_mode="browser")

        assert resp.status_code == 200
        data = resp.json()
        assert "Welcome to the SPA" in data["content_markdown"]

    def test_browser_mode_returns_502_on_browser_error(self):
        with patch(
            "app.routers.scrape.fetch_url_with_browser",
            new=AsyncMock(side_effect=RuntimeError("crashed")),
        ):
            resp = _post(render_mode="browser")

        assert resp.status_code == 502

    def test_browser_mode_returns_400_on_invalid_url(self):
        with patch(
            "app.routers.scrape.fetch_url_with_browser",
            new=AsyncMock(side_effect=ValueError("invalid url")),
        ):
            resp = _post(render_mode="browser")

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# include_images / include_links filtering
# ---------------------------------------------------------------------------

class TestScrapeFiltering:
    def test_include_images_false(self):
        html = (
            _STATIC_HTML.replace(
                "</main>",
                '<img src="/photo.jpg"></main>',
            )
        )
        with patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=html)):
            resp = _post(include_images=False, render_mode="http")

        assert resp.status_code == 200
        assert resp.json()["images"] == []

    def test_include_links_false(self):
        html = _STATIC_HTML.replace(
            "</main>",
            '<a href="https://example.com/other">other</a></main>',
        )
        with patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=html)):
            resp = _post(include_links=False, render_mode="http")

        assert resp.status_code == 200
        assert resp.json()["links"] == []


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class TestScrapeResponseSchema:
    def test_response_contains_platform_type(self):
        with patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_STATIC_HTML)):
            resp = _post(render_mode="http")

        assert resp.status_code == 200
        assert "platform_type" in resp.json()

    def test_response_contains_all_fields(self):
        with patch("app.routers.scrape.fetch_url", new=AsyncMock(return_value=_STATIC_HTML)):
            resp = _post(render_mode="http")

        data = resp.json()
        for field in (
            "url", "title", "description", "content_markdown",
            "images", "videos", "links", "word_count", "platform_type",
        ):
            assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestScrapeErrorHandling:
    def test_timeout_returns_504(self):
        import httpx

        with patch(
            "app.routers.scrape.fetch_url",
            new=AsyncMock(side_effect=httpx.TimeoutException("timed out")),
        ):
            resp = _post(render_mode="http")

        assert resp.status_code == 504

    def test_http_status_error_returns_502(self):
        import httpx

        mock_response = AsyncMock()
        mock_response.status_code = 404
        exc = httpx.HTTPStatusError("not found", request=AsyncMock(), response=mock_response)

        with patch("app.routers.scrape.fetch_url", new=AsyncMock(side_effect=exc)):
            resp = _post(render_mode="http")

        assert resp.status_code == 502

    def test_invalid_url_returns_422(self):
        """Pydantic validates HttpUrl so a bad URL is rejected before the handler."""
        resp = _post(url="not-a-url")
        assert resp.status_code == 422
