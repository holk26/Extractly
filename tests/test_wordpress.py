"""Tests for wordpress._item_to_page shortcode stripping and dummy-page filtering."""

from app.services.wordpress import _item_to_page

_BASE = "https://example.com"


def _make_item(content_rendered: str, title: str = "Test Page") -> dict:
    return {
        "link": f"{_BASE}/test-page/",
        "slug": "test-page",
        "title": {"rendered": title},
        "content": {"rendered": content_rendered},
        "excerpt": {"rendered": ""},
    }


class TestItemToPageShortcodeStripping:
    def test_divi_shortcodes_are_stripped(self):
        item = _make_item(
            "[et_pb_section fb_built='1']"
            "<p>Real content here.</p>"
            "[/et_pb_section]"
        )
        page = _item_to_page(item, _BASE)
        assert page is not None
        assert "et_pb" not in page.content
        assert "Real content here" in page.content

    def test_wpbakery_shortcodes_are_stripped(self):
        item = _make_item(
            "[vc_row][vc_column width='1/1']<p>WPBakery content</p>[/vc_column][/vc_row]"
        )
        page = _item_to_page(item, _BASE)
        assert page is not None
        assert "vc_row" not in page.content
        assert "WPBakery content" in page.content

    def test_content_markdown_does_not_contain_shortcodes(self):
        item = _make_item(
            "[et_pb_row]<h2>Title</h2><p>Body text.</p>[/et_pb_row]"
        )
        page = _item_to_page(item, _BASE)
        assert page is not None
        assert "et_pb" not in page.content_markdown


class TestItemToPageDummyPageFilter:
    def test_empty_content_returns_none(self):
        item = _make_item("")
        assert _item_to_page(item, _BASE) is None

    def test_only_shortcodes_returns_none(self):
        item = _make_item("[et_pb_section][/et_pb_section]")
        assert _item_to_page(item, _BASE) is None

    def test_whitespace_only_returns_none(self):
        item = _make_item("   \n\t  ")
        assert _item_to_page(item, _BASE) is None

    def test_valid_content_is_returned(self):
        item = _make_item("<p>This is real, substantive content.</p>")
        page = _item_to_page(item, _BASE)
        assert page is not None
        assert page.url == f"{_BASE}/test-page/"

    def test_missing_link_returns_none(self):
        item = {
            "link": "",
            "slug": "no-link",
            "title": {"rendered": "No Link"},
            "content": {"rendered": "<p>Some content</p>"},
            "excerpt": {"rendered": ""},
        }
        assert _item_to_page(item, _BASE) is None
