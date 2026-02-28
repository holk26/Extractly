from bs4 import BeautifulSoup, NavigableString, Tag

# Tags whose entire subtree should be removed
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
}

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


def sanitize(html: str) -> BeautifulSoup:
    """Remove noise elements from *html* and return the cleaned BeautifulSoup tree."""
    soup = BeautifulSoup(html, "lxml")

    # Remove tags that should never appear in clean output
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # Remove elements whose class/id indicates noise (nav, ads, tracking, …)
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if _has_noise_attr(tag):
            tag.decompose()

    return soup
