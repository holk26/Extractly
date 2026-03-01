"""Tests for sanitizer.strip_shortcodes and sanitize."""

from app.services.sanitizer import strip_shortcodes, sanitize


class TestStripShortcodes:
    def test_strips_divi_section_tags(self):
        html = "[et_pb_section fb_built='1'][/et_pb_section]"
        assert strip_shortcodes(html) == ""

    def test_strips_divi_row_and_column(self):
        content = "[et_pb_row][et_pb_column type='4_4']Hello[/et_pb_column][/et_pb_row]"
        result = strip_shortcodes(content)
        assert "et_pb" not in result
        assert "Hello" in result

    def test_strips_self_closing_shortcode(self):
        result = strip_shortcodes("Before [gallery ids='1,2,3'] After")
        assert "[gallery" not in result
        assert "Before" in result
        assert "After" in result

    def test_strips_closing_shortcode(self):
        result = strip_shortcodes("[/et_pb_section]")
        assert result == ""

    def test_no_shortcodes_unchanged(self):
        html = "<p>Regular HTML content without shortcodes.</p>"
        assert strip_shortcodes(html) == html

    def test_mixed_html_and_shortcodes(self):
        html = "<p>Text</p>[et_pb_section]<p>More text</p>[/et_pb_section]"
        result = strip_shortcodes(html)
        assert "[et_pb_section]" not in result
        assert "[/et_pb_section]" not in result
        assert "<p>Text</p>" in result
        assert "<p>More text</p>" in result

    def test_strips_wpbakery_shortcodes(self):
        html = "[vc_row][vc_column width='1/1']<p>Content</p>[/vc_column][/vc_row]"
        result = strip_shortcodes(html)
        assert "vc_row" not in result
        assert "<p>Content</p>" in result

    def test_empty_string(self):
        assert strip_shortcodes("") == ""

    def test_uppercase_shortcode(self):
        result = strip_shortcodes("[ET_PB_SECTION]content[/ET_PB_SECTION]")
        assert "ET_PB_SECTION" not in result
        assert "content" in result
