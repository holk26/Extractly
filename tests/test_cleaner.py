"""Tests for app.services.cleaner.clean_markdown."""

from app.services.cleaner import clean_markdown


class TestCleanMarkdownEmailObfuscation:
    def test_removes_cloudflare_email_placeholder(self):
        text = "Contact us at [email\u00a0protected] for support."
        result = clean_markdown(text)
        assert "[email" not in result
        assert "protected]" not in result

    def test_removes_email_protected_literal(self):
        text = "Send a message to [email protected]."
        result = clean_markdown(text)
        assert "[email" not in result

    def test_removes_html_entity_email_variant(self):
        text = "Write to [email&#160;protected] today."
        result = clean_markdown(text)
        assert "protected" not in result

    def test_preserves_surrounding_text(self):
        text = "Call us or email [email\u00a0protected] or visit our office."
        result = clean_markdown(text)
        assert "Call us or email" in result
        assert "or visit our office" in result

    def test_removes_tel_uri_noise(self):
        text = "Phone: tel:+1%20555%20123%204567 – available 9-5."
        result = clean_markdown(text)
        assert "tel:" not in result

    def test_removes_stray_html_numeric_entities(self):
        text = "Price&#58; &#36;10&#46;99"
        result = clean_markdown(text)
        assert "&#" not in result


class TestCleanMarkdownCookieBanners:
    def test_removes_this_website_uses_cookies(self):
        text = "This website uses cookies to improve your experience."
        result = clean_markdown(text)
        assert "uses cookies" not in result

    def test_removes_we_use_cookies(self):
        text = "We use cookies to personalise content and ads."
        result = clean_markdown(text)
        assert "use cookies" not in result

    def test_removes_accept_cookies(self):
        text = "Click here to accept all cookies and continue browsing."
        result = clean_markdown(text)
        assert "accept all cookies" not in result

    def test_removes_cookie_policy_reference(self):
        text = "Read our cookie policy for more information."
        result = clean_markdown(text)
        assert "cookie policy" not in result

    def test_preserves_unrelated_content(self):
        text = "## Main Article\n\nThis is the actual article content about cooking."
        result = clean_markdown(text)
        assert "Main Article" in result
        assert "actual article content about cooking" in result


class TestCleanMarkdownStructural:
    def test_collapses_excessive_blank_lines(self):
        text = "First paragraph.\n\n\n\n\nSecond paragraph."
        result = clean_markdown(text)
        assert "\n\n\n" not in result
        assert "First paragraph." in result
        assert "Second paragraph." in result

    def test_double_blank_line_unchanged(self):
        text = "Paragraph one.\n\nParagraph two."
        result = clean_markdown(text)
        assert result == "Paragraph one.\n\nParagraph two."

    def test_removes_empty_markdown_links(self):
        text = "Some text [  ](https://example.com) more text."
        result = clean_markdown(text)
        assert "[  ]" not in result
        assert "Some text" in result
        assert "more text" in result

    def test_strips_leading_trailing_whitespace(self):
        text = "   \n\nHello world.\n\n   "
        result = clean_markdown(text)
        assert result == "Hello world."

    def test_empty_string_unchanged(self):
        assert clean_markdown("") == ""

    def test_normal_content_preserved(self):
        text = "## Title\n\nSome **bold** and _italic_ content.\n\n- Item one\n- Item two"
        result = clean_markdown(text)
        assert "## Title" in result
        assert "**bold**" in result
        assert "_italic_" in result
        assert "- Item one" in result
