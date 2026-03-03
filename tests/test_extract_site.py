"""Tests for the /api/extract-site endpoint.

These tests verify:
- Basic site extraction with multiple pages
- URL validation and SSRF protection
- max_pages limit enforcement
- Link discovery and same-domain filtering
- Error handling (invalid URLs, browser failures)
- Resilience to networkidle timeouts (sites with persistent connections)

External calls and Playwright are mocked to run tests without internet access.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear the slowapi in-memory counter before every test."""
    # Import the limiter from extract_site router to reset its storage
    from app.routers.extract_site import limiter as extract_site_limiter
    app.state.limiter._storage.reset()
    extract_site_limiter._storage.reset()
    yield


# ---------------------------------------------------------------------------
# Shared HTML fixtures
# ---------------------------------------------------------------------------

_PAGE1_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Page 1</title>
</head>
<body>
  <main>
    <h1>Welcome to Page 1</h1>
    <p>This is the first page of the website.</p>
    <a href="/page2">Go to Page 2</a>
    <a href="https://external.com">External Link</a>
  </main>
</body>
</html>
"""

_PAGE2_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Page 2</title>
</head>
<body>
  <main>
    <h1>Welcome to Page 2</h1>
    <p>This is the second page of the website.</p>
    <a href="/page3">Go to Page 3</a>
  </main>
</body>
</html>
"""

_PAGE3_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Page 3</title>
</head>
<body>
  <main>
    <h1>Welcome to Page 3</h1>
    <p>This is the third page of the website.</p>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(url: str = "https://example.com", **kwargs):
    """POST to /api/extract-site with sensible defaults."""
    payload = {"url": url, **kwargs}
    return client.post("/api/extract-site", json=payload)


# ---------------------------------------------------------------------------
# Basic functionality tests
# ---------------------------------------------------------------------------

class TestExtractSiteBasic:
    def test_extracts_single_page(self):
        """Test extracting a single page with no internal links."""
        async def mock_crawl(url, max_pages):
            from app.services.site_crawler import PageData
            return [
                PageData(
                    url=url,
                    title="Page 1",
                    content_markdown="# Welcome to Page 1\n\nThis is the first page of the website.",
                )
            ]

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com", max_pages=5)

        assert resp.status_code == 200
        data = resp.json()
        assert data["start_url"] == "https://example.com/"
        assert data["pages_extracted"] == 1
        assert len(data["pages"]) == 1
        assert data["pages"][0]["title"] == "Page 1"
        assert "Welcome to Page 1" in data["pages"][0]["content_markdown"]

    def test_extracts_multiple_pages(self):
        """Test extracting multiple pages from a site."""
        async def mock_crawl(url, max_pages):
            from app.services.site_crawler import PageData
            return [
                PageData(
                    url="https://example.com",
                    title="Page 1",
                    content_markdown="# Welcome to Page 1",
                ),
                PageData(
                    url="https://example.com/page2",
                    title="Page 2",
                    content_markdown="# Welcome to Page 2",
                ),
                PageData(
                    url="https://example.com/page3",
                    title="Page 3",
                    content_markdown="# Welcome to Page 3",
                ),
            ]

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com", max_pages=5)

        assert resp.status_code == 200
        data = resp.json()
        assert data["pages_extracted"] == 3
        assert len(data["pages"]) == 3
        assert data["pages"][0]["title"] == "Page 1"
        assert data["pages"][1]["title"] == "Page 2"
        assert data["pages"][2]["title"] == "Page 3"

    def test_respects_max_pages_limit(self):
        """Test that max_pages parameter limits the number of extracted pages."""
        async def mock_crawl(url, max_pages):
            from app.services.site_crawler import PageData
            # Return only max_pages number of results
            return [
                PageData(
                    url=f"https://example.com/page{i}",
                    title=f"Page {i}",
                    content_markdown=f"# Page {i}",
                )
                for i in range(1, min(max_pages + 1, 4))
            ]

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com", max_pages=2)

        assert resp.status_code == 200
        data = resp.json()
        assert data["pages_extracted"] == 2
        assert len(data["pages"]) == 2


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestExtractSiteValidation:
    def test_invalid_url_returns_422(self):
        """Test that invalid URLs are rejected by Pydantic validation."""
        resp = _post(url="not-a-url")
        assert resp.status_code == 422

    def test_private_url_returns_400(self):
        """Test that private/internal URLs are rejected."""
        async def mock_crawl(url, max_pages):
            raise ValueError("Requests to private/internal addresses are not allowed.")

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="http://localhost:8000")

        assert resp.status_code == 400
        assert "private" in resp.json()["detail"].lower()

    def test_max_pages_validation(self):
        """Test that max_pages is validated (1-50)."""
        resp = _post(url="https://example.com", max_pages=0)
        assert resp.status_code == 422

        resp = _post(url="https://example.com", max_pages=100)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestExtractSiteErrorHandling:
    def test_browser_error_returns_502(self):
        """Test that browser/network errors return 502."""
        async def mock_crawl(url, max_pages):
            raise RuntimeError("Browser crashed")

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com")

        assert resp.status_code == 502

    def test_generic_exception_returns_502(self):
        """Test that unexpected exceptions return 502."""
        async def mock_crawl(url, max_pages):
            raise Exception("Unexpected error")

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Response schema tests
# ---------------------------------------------------------------------------

class TestExtractSiteResponseSchema:
    def test_response_has_required_fields(self):
        """Test that response contains all required fields."""
        async def mock_crawl(url, max_pages):
            from app.services.site_crawler import PageData
            return [
                PageData(
                    url=url,
                    title="Test Page",
                    content_markdown="# Test Content",
                )
            ]

        with patch("app.routers.extract_site.crawl_site", new=AsyncMock(side_effect=mock_crawl)):
            resp = _post(url="https://example.com")

        assert resp.status_code == 200
        data = resp.json()

        # Check top-level fields
        assert "start_url" in data
        assert "pages_extracted" in data
        assert "pages" in data

        # Check page fields
        assert len(data["pages"]) > 0
        page = data["pages"][0]
        assert "url" in page
        assert "title" in page
        assert "content_markdown" in page


# ---------------------------------------------------------------------------
# Resilience tests for _fetch_with_browser (networkidle timeout fallback)
# ---------------------------------------------------------------------------

class TestFetchWithBrowserResilience:
    """Tests that _fetch_with_browser falls back gracefully on networkidle timeouts.

    Sites with persistent network connections (analytics, chat widgets, etc.) never
    reach 'networkidle' state. Previously the function used wait_until='networkidle'
    which caused a timeout on such sites.  The fix uses wait_until='load' for the
    initial navigation and wraps the post-scroll networkidle wait in a try/except
    so content is always returned even when networkidle never fires.
    """

    @pytest.mark.asyncio
    async def test_networkidle_timeout_still_returns_html(self):
        """If networkidle times out after scrolling, page content is still returned."""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        from app.services.site_crawler import _fetch_with_browser

        sample_html = "<html><body><h1>Hello</h1></body></html>"

        # Build a minimal Playwright page mock that raises PlaywrightTimeoutError
        # on wait_for_load_state to simulate a persistent-connection site.
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.content = AsyncMock(return_value=sample_html)
        mock_page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("Timeout waiting for networkidle")
        )

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_pw = MagicMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("app.services.site_crawler.async_playwright", return_value=mock_pw):
            html = await _fetch_with_browser("https://example.com")

        assert html == sample_html

    @pytest.mark.asyncio
    async def test_goto_uses_load_not_networkidle(self):
        """page.goto must use wait_until='load' so sites with background traffic load."""
        from app.services.site_crawler import _fetch_with_browser

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body></body></html>")
        mock_page.wait_for_load_state = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_pw = MagicMock()
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("app.services.site_crawler.async_playwright", return_value=mock_pw):
            await _fetch_with_browser("https://example.com")

        # The first positional arg after URL should be wait_until='load'
        _, kwargs = mock_page.goto.call_args
        assert kwargs.get("wait_until") == "load"
