"""Tests for sanitizer.strip_shortcodes and sanitize."""

from app.services.sanitizer import sanitize, strip_shortcodes


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


class TestSanitize:
    def test_removes_script_tags(self):
        soup = sanitize("<p>Text</p><script>alert('xss')</script>")
        assert "alert" not in soup.get_text()

    def test_removes_style_tags(self):
        soup = sanitize("<style>body { color: red; }</style><p>Text</p>")
        assert "color" not in soup.get_text()

    def test_removes_svg_tags(self):
        soup = sanitize("<p>Hello</p><svg><path d='M0 0 L100 100'/></svg>")
        text = soup.get_text()
        assert "M0 0" not in text
        assert "Hello" in text

    def test_removes_canvas_tags(self):
        soup = sanitize("<p>Content</p><canvas>fallback</canvas>")
        assert "fallback" not in soup.get_text()
        assert "Content" in soup.get_text()

    def test_removes_template_tags(self):
        soup = sanitize("<p>Real</p><template><div>tmpl js code</div></template>")
        assert "tmpl js code" not in soup.get_text()
        assert "Real" in soup.get_text()

    def test_removes_html_comments(self):
        soup = sanitize("<p>Visible</p><!-- hidden comment -->")
        assert "hidden comment" not in str(soup)

    def test_removes_display_none_elements(self):
        soup = sanitize('<p>Visible</p><div style="display:none">Hidden</div>')
        assert "Hidden" not in soup.get_text()
        assert "Visible" in soup.get_text()

    def test_removes_visibility_hidden_elements(self):
        soup = sanitize('<span style="visibility: hidden">Ghost</span><p>Real</p>')
        assert "Ghost" not in soup.get_text()
        assert "Real" in soup.get_text()

    def test_strips_inline_style_attribute(self):
        soup = sanitize('<p style="color:red;font-size:14px">Styled text</p>')
        # The text should survive but the style attribute must be gone
        assert "Styled text" in soup.get_text()
        p = soup.find("p")
        assert p is not None
        assert p.get("style") is None

    def test_strips_event_handler_attributes(self):
        soup = sanitize('<a href="/page" onclick="doSomething()">Link</a>')
        a = soup.find("a")
        assert a is not None
        assert a.get("onclick") is None
        # href should still be present
        assert a.get("href") == "/page"

    def test_normal_content_preserved(self):
        html = "<h1>Title</h1><p>Paragraph <strong>bold</strong> text.</p>"
        soup = sanitize(html)
        assert "Title" in soup.get_text()
        assert "Paragraph" in soup.get_text()
        assert "bold" in soup.get_text()


class TestSanitizeStructuralNoise:
    def test_removes_nav_tag(self):
        soup = sanitize("<nav><a href='/'>Home</a><a href='/about'>About</a></nav><p>Content</p>")
        assert "Home" not in soup.get_text()
        assert "Content" in soup.get_text()

    def test_removes_aside_tag(self):
        soup = sanitize("<p>Main content</p><aside><p>Sidebar widget</p></aside>")
        assert "Sidebar widget" not in soup.get_text()
        assert "Main content" in soup.get_text()

    def test_removes_form_tag(self):
        soup = sanitize("<p>Article text</p><form><input type='text'><button>Submit</button></form>")
        assert "Submit" not in soup.get_text()
        assert "Article text" in soup.get_text()

    def test_removes_body_direct_child_header(self):
        html = "<body><header><a href='/'>Logo</a><nav>Menu</nav></header><main><p>Article</p></main></body>"
        soup = sanitize(html)
        assert "Logo" not in soup.get_text()
        assert "Article" in soup.get_text()

    def test_removes_body_direct_child_footer(self):
        html = "<body><main><p>Content</p></main><footer><p>Copyright 2024</p></footer></body>"
        soup = sanitize(html)
        assert "Copyright 2024" not in soup.get_text()
        assert "Content" in soup.get_text()

    def test_preserves_article_level_header(self):
        html = (
            "<body>"
            "<header><a href='/'>Site Logo</a></header>"
            "<main><article>"
            "<header><h1>Article Title</h1><p>By Author</p></header>"
            "<p>Article body text.</p>"
            "</article></main>"
            "</body>"
        )
        soup = sanitize(html)
        # Site-level header is removed
        assert "Site Logo" not in soup.get_text()
        # Article-level header (not a direct body child) is kept
        assert "Article Title" in soup.get_text()
        assert "Article body text." in soup.get_text()

    def test_preserves_article_level_footer(self):
        html = (
            "<body>"
            "<main><article>"
            "<p>Content here.</p>"
            "<footer><p>Tags: python, scraping</p></footer>"
            "</article></main>"
            "<footer><p>Site copyright</p></footer>"
            "</body>"
        )
        soup = sanitize(html)
        # Article-level footer is kept (inside <article>)
        assert "Tags: python, scraping" in soup.get_text()
        # Site-level footer is removed
        assert "Site copyright" not in soup.get_text()
