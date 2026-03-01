import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# Matches WordPress shortcode tags such as [et_pb_section ...] or [/et_pb_section]
_SHORTCODE_RE = re.compile(r"\[/?[a-z_\-]+(?:\s[^\]]*?)?\]", re.IGNORECASE)

# Matches `display:none` or `visibility:hidden` in inline style attributes
_HIDDEN_STYLE_RE = re.compile(
    r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE
)

# Tags whose entire subtree should be removed (non-content / binary / scripting)
_REMOVE_TAGS = {
    "script",
    "style",
    "noscript",
    "iframe",
    "object",
    "embed",
    "applet",
    "link",
    "meta",
    # Vector / canvas graphics produce raw coordinate/path noise in plain text
    "svg",
    "canvas",
    # Template elements may contain raw JS template markup
    "template",
}

# HTML attributes that contain CSS or JavaScript and should be stripped
# from every element that survives the tree pruning step.
_JUNK_ATTRS = re.compile(
    r"^(style|on\w+)$", re.IGNORECASE
)

# CSS classes / ids that strongly indicate non-content elements
_NOISE_KEYWORDS = {
    "nav",
    "navbar",
    "navigation",
    "menu",
    "sidebar",
    "side-bar",
    "banner",
    "popup",
    "modal",
    "cookie",
    "gdpr",
    "ads",
    "advertisement",
    "tracking",
    "footer",
    "header",
    "breadcrumb",
    "pagination",
    "social",
    "share",
    "related",
    "recommend",
    "subscribe",
    "newsletter",
    "promo",
    "overlay",
    # WordPress-specific noise
    "comment",
    "widget",
    "author-info",
    "author-bio",
    "author-box",
    "post-meta",
    "entry-meta",
    "wp-block-latest-posts",
    "wp-block-categories",
    "wp-block-archives",
    "wp-block-tag-cloud",
    "site-branding",
    "site-footer",
    "site-header",
    "search-form",
}


def _has_noise_attr(tag: Tag) -> bool:
    """Return True when a tag's id or class suggests it is non-content."""
    if not tag.attrs:
        return False
    attrs_to_check = []
    if tag.get("id"):
        attrs_to_check.append(str(tag["id"]).lower())
    for cls in tag.get("class", []):
        attrs_to_check.append(cls.lower())

    return any(keyword in attr for attr in attrs_to_check for keyword in _NOISE_KEYWORDS)


def strip_shortcodes(html: str) -> str:
    """Remove WordPress shortcode tags (e.g. ``[et_pb_section ...]``) from ``html``.

    Some page builders (Divi, WPBakery, …) leave shortcode markup in
    ``content.rendered`` when the REST API bypasses the builder's rendering
    pipeline.  This function strips those text-level shortcode patterns so
    they do not pollute the final content.
    """
    return _SHORTCODE_RE.sub("", html)


def sanitize(html: str) -> BeautifulSoup:
    """Remove noise elements from *html* and return the cleaned BeautifulSoup tree."""
    soup = BeautifulSoup(html, "lxml")

    # Remove tags that should never appear in clean output
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # Remove HTML comment nodes (may contain debugging info or conditional blocks)
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove elements whose class/id indicates noise (nav, ads, tracking, …)
    # Also remove elements hidden via inline CSS (display:none / visibility:hidden)
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if _has_noise_attr(tag):
            tag.decompose()
            continue
        inline_style = tag.get("style", "")
        if inline_style and _HIDDEN_STYLE_RE.search(inline_style):
            tag.decompose()
            continue
        # Strip inline CSS and event-handler attributes so they cannot leak
        # into the Markdown output or pollute plain-text extraction.
        junk = [attr for attr in tag.attrs if _JUNK_ATTRS.match(attr)]
        for attr in junk:
            del tag[attr]

    return soup
