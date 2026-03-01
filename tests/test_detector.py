"""Tests for app.services.detector.detect_platform."""

from app.services.detector import _SPA_MIN_WORDS, detect_platform


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spa_html(extra: str = "") -> str:
    """Minimal HTML shell that a SPA would return over plain HTTP."""
    return f'<!DOCTYPE html><html><head><title>App</title></head><body>{extra}</body></html>'


def _ssr_html(body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><title>Page</title></head>"
        f"<body><main>{body}</main></body></html>"
    )


# ---------------------------------------------------------------------------
# WordPress detection
# ---------------------------------------------------------------------------

class TestDetectWordPress:
    def test_wp_content_path(self):
        html = '<img src="/wp-content/uploads/2024/photo.jpg">'
        assert detect_platform(html, 500) == "wordpress"

    def test_wp_includes_path(self):
        html = '<script src="/wp-includes/js/jquery.min.js"></script>'
        assert detect_platform(html, 200) == "wordpress"

    def test_wp_rest_api_link(self):
        html = '<link rel="https://api.w.org/" href="https://example.com/wp-json/">'
        assert detect_platform(html, 100) == "wordpress"

    def test_wp_generator_meta(self):
        html = '<meta name="generator" content="WordPress 6.4.2">'
        assert detect_platform(html, 80) == "wordpress"

    def test_wordpress_takes_priority_over_spa_markers(self):
        # A page can have both WP and React markers (e.g. headless WP + React).
        # WordPress should win because the WP API is the primary integration path.
        html = (
            '/wp-content/themes/mysite/style.css'
            '<div id="root"></div>'
        )
        assert detect_platform(html, 0) == "wordpress"


# ---------------------------------------------------------------------------
# SPA detection
# ---------------------------------------------------------------------------

class TestDetectSPA:
    def test_react_root_with_thin_content(self):
        html = _spa_html('<div id="root"></div>')
        assert detect_platform(html, 0) == "spa"

    def test_next_mount_with_thin_content(self):
        html = _spa_html('<div id="__next"></div>')
        assert detect_platform(html, 5) == "spa"

    def test_vue_app_mount_with_thin_content(self):
        html = _spa_html('<div id="app"></div>')
        assert detect_platform(html, 0) == "spa"

    def test_nuxt_mount_with_thin_content(self):
        html = _spa_html('<div id="__nuxt"></div>')
        assert detect_platform(html, 3) == "spa"

    def test_next_data_script_with_thin_content(self):
        html = _spa_html('<script id="__NEXT_DATA__" type="application/json">{}</script>')
        assert detect_platform(html, 0) == "spa"

    def test_nuxt_window_var_with_thin_content(self):
        html = _spa_html('<script>window.__NUXT__={}</script>')
        assert detect_platform(html, 0) == "spa"

    def test_angular_ng_version_with_thin_content(self):
        html = _spa_html('<app-root ng-version="17.0.0"></app-root>')
        assert detect_platform(html, 0) == "spa"

    def test_react_data_reactroot_with_thin_content(self):
        html = _spa_html('<div data-reactroot=""></div>')
        assert detect_platform(html, 10) == "spa"

    def test_svelte_component_with_thin_content(self):
        html = _spa_html('<svelte:options accessors/>')
        assert detect_platform(html, 0) == "spa"

    def test_spa_marker_but_sufficient_content_is_ssr(self):
        """SSR-mode Next.js: marker present but the server already sent content."""
        html = _spa_html('<div id="__next"></div><script>__NEXT_DATA__={}</script>')
        # word_count is well above the SPA threshold → SSR classification
        assert detect_platform(html, _SPA_MIN_WORDS + 1) == "ssr"

    def test_spa_marker_exactly_at_threshold_is_ssr(self):
        """Word count == _SPA_MIN_WORDS is NOT below the threshold → ssr."""
        html = _spa_html('<div id="root"></div>')
        assert detect_platform(html, _SPA_MIN_WORDS) == "ssr"

    def test_thin_content_without_spa_markers_is_ssr(self):
        """A thin page with no SPA markers is classified as ssr, not spa."""
        html = "<html><body><p>Hi</p></body></html>"
        assert detect_platform(html, 1) == "ssr"


# ---------------------------------------------------------------------------
# SSR / static detection
# ---------------------------------------------------------------------------

class TestDetectSSR:
    def test_plain_ssr_page(self):
        html = _ssr_html("<h1>Welcome</h1><p>" + "word " * 50 + "</p>")
        assert detect_platform(html, 55) == "ssr"

    def test_empty_html_no_markers_is_ssr(self):
        assert detect_platform("<html></html>", 0) == "ssr"

    def test_large_static_page(self):
        html = "<html><body>" + "<p>content</p>" * 100 + "</body></html>"
        assert detect_platform(html, 200) == "ssr"
