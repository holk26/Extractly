"""Tests for sanitizer.strip_shortcodes and sanitize."""

from app.services.parsing.sanitizer import sanitize, strip_shortcodes


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


class TestSanitizePageBuilderContent:
    """Ensure content from JS page builders (Elementor, Divi, etc.) is preserved."""

    def test_preserves_elementor_widget_container_content(self):
        """Elementor wraps content in elementor-widget-container — must not be stripped."""
        html = (
            "<div class='elementor-widget-wrap'>"
            "<div class='elementor-widget-container'>"
            "<p>Our services include parking management.</p>"
            "</div>"
            "</div>"
        )
        soup = sanitize(html)
        assert "Our services include parking management." in soup.get_text()

    def test_preserves_elementor_text_editor_content(self):
        """Elementor text-editor widget must survive sanitization."""
        html = (
            "<div class='elementor-widget-text-editor elementor-widget'>"
            "<div class='elementor-widget-container'>"
            "<p>Company overview text.</p>"
            "</div>"
            "</div>"
        )
        soup = sanitize(html)
        assert "Company overview text." in soup.get_text()

    def test_preserves_elementor_heading_widget(self):
        """Elementor heading widget must survive sanitization."""
        html = (
            "<div class='elementor-widget-heading elementor-widget'>"
            "<div class='elementor-widget-container'>"
            "<h2 class='elementor-heading-title'>About Us</h2>"
            "</div>"
            "</div>"
        )
        soup = sanitize(html)
        assert "About Us" in soup.get_text()

    def test_sidebar_widget_area_still_removed(self):
        """WordPress sidebar widget areas (class=sidebar) remain filtered."""
        html = (
            "<body>"
            "<main><p>Main content</p></main>"
            "<div class='sidebar'>"
            "<div class='widget widget_recent_posts'><p>Recent post</p></div>"
            "</div>"
            "</body>"
        )
        soup = sanitize(html)
        assert "Main content" in soup.get_text()
        assert "Recent post" not in soup.get_text()


class TestSanitizeStructuralTagProtection:
    """Ensure structural HTML elements are never stripped by the noise filter.

    WordPress themes add classes like `has-header-image` or `overlay-header`
    to the `<body>` tag.  The substring "header" matched the noise keyword and
    caused the entire body to be decomposed, leaving only the `<title>` text
    in the output.  `html`, `body`, `main`, and `article` must always
    survive regardless of their class/id attributes.
    """

    def test_body_with_has_header_image_class_preserved(self):
        """<body class='has-header-image'> must NOT be stripped despite matching 'header'."""
        html = (
            "<body class='page elementor-default has-header-image'>"
            "<main><p>Page content here.</p></main>"
            "</body>"
        )
        soup = sanitize(html)
        assert soup.find("body") is not None
        assert "Page content here." in soup.get_text()

    def test_body_with_overlay_header_class_preserved(self):
        """<body class='overlay-header'> must NOT be stripped."""
        html = (
            "<body class='page overlay-header'>"
            "<main><p>Article text.</p></main>"
            "</body>"
        )
        soup = sanitize(html)
        assert soup.find("body") is not None
        assert "Article text." in soup.get_text()

    def test_body_with_has_footer_image_class_preserved(self):
        """<body class='has-footer-image'> must NOT be stripped."""
        html = (
            "<body class='page has-footer-image'>"
            "<main><p>Body content.</p></main>"
            "</body>"
        )
        soup = sanitize(html)
        assert soup.find("body") is not None
        assert "Body content." in soup.get_text()

    def test_main_with_noise_class_preserved(self):
        """<main class='site-main has-navigation-overlay'> must NOT be stripped."""
        html = (
            "<body>"
            "<main class='site-main has-navigation-overlay'>"
            "<p>Main content.</p>"
            "</main>"
            "</body>"
        )
        soup = sanitize(html)
        assert soup.find("main") is not None
        assert "Main content." in soup.get_text()

    def test_article_with_noise_class_preserved(self):
        """<article class='hentry post-navigation'> must NOT be stripped."""
        html = (
            "<body>"
            "<article class='hentry post-navigation'>"
            "<p>Article content.</p>"
            "</article>"
            "</body>"
        )
        soup = sanitize(html)
        assert soup.find("article") is not None
        assert "Article content." in soup.get_text()

    def test_no_title_only_output_when_body_has_header_class(self):
        """Full Elementor page with has-header-image body: content not reduced to title."""
        html = """<!DOCTYPE html>
<html>
<head><title>Total Space Incorporation – Effective Usage of Any Space</title></head>
<body class="page page-id-10 elementor-default has-header-image">
  <header id="masthead" class="site-header">
    <p class="site-description">Effective Usage of Any Space</p>
  </header>
  <main id="main" class="site-main" role="main">
    <article>
      <div class="entry-content">
        <div class="elementor elementor-10">
          <section class="elementor-section elementor-top-section">
            <div class="elementor-widget-wrap elementor-element-populated">
              <div class="elementor-widget elementor-widget-heading">
                <div class="elementor-widget-container">
                  <h1>RETHINK SPACE</h1>
                  <p>Parking, pool, and green space management.</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </article>
  </main>
  <footer id="colophon" class="site-footer"><p>Copyright</p></footer>
</body>
</html>"""
        from markdownify import markdownify
        from app.services.crawling.site_crawler import _find_main_content

        clean_soup = sanitize(html)
        node = _find_main_content(clean_soup)
        md = markdownify(str(node), heading_style="ATX").strip()

        assert "RETHINK SPACE" in md
        assert "Parking, pool, and green space management." in md
        # Must NOT be reduced to just the page title
        assert md != "Total Space Incorporation – Effective Usage of Any Space"
