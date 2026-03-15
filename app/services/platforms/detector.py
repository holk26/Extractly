"""Platform / technology detection from page HTML.

Given the raw HTML returned by an HTTP GET and the word-count produced by the
extractor, :func:`detect_platform` classifies the page into one of four
platform types so the scrape router can choose the right rendering path.

Platform types
--------------
``"wordpress"``
    WordPress-powered site (identified by ``/wp-content/`` paths, the REST-API
    link header, or the ``<meta name="generator">`` tag).

``"spa"``
    JavaScript single-page application.  The HTTP-fetched HTML contains SPA
    framework fingerprints (React, Vue, Angular, Next.js, Nuxt, …) **and** the
    extractor found very little readable content—a clear sign that content is
    rendered client-side and a headless browser is required.

``"ssr"``
    Server-side rendered page (Next.js in SSR mode, Nuxt SSR, Django, Rails,
    Laravel, plain PHP, …).  The HTTP response already contains sufficient
    readable content.

``"static"``
    Statically generated or plain HTML site with no recognised CMS/framework
    markers.
"""

import re
from typing import Literal

PlatformType = Literal["wordpress", "spa", "ssr", "static"]

# ---------------------------------------------------------------------------
# WordPress fingerprints
# ---------------------------------------------------------------------------
_WP_PATTERN = re.compile(
    r"/wp-content/"
    r"|/wp-includes/"
    # <link rel="https://api.w.org/"> — WP REST-API link relation
    r'|rel=["\']https://api\.w\.org/'
    # <meta name="generator" content="WordPress …">
    r'|<meta[^>]+name=["\']generator["\'][^>]+content=["\']WordPress',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# SPA framework fingerprints
# Present in the *un-rendered* HTML shell when a SPA mounts on the server.
# ---------------------------------------------------------------------------
_SPA_PATTERN = re.compile(
    # React / Next.js mount targets
    r'<div\s[^>]*\bid=["\']root["\"]'
    r'|<div\s[^>]*\bid=["\']__next["\"]'
    # Vue / generic SPA mount target
    r'|<div\s[^>]*\bid=["\']app["\"]'
    # Nuxt.js
    r'|<div\s[^>]*\bid=["\']__nuxt["\"]'
    r"|window\.__NUXT__"
    # Next.js inline data script
    r"|__NEXT_DATA__"
    # Angular attribute added at runtime (present in HTML template)
    r"|ng-version="
    # React legacy server attribute
    r"|data-reactroot"
    # Svelte / generic "svelte-*" component roots
    r"|<svelte:",
    re.IGNORECASE,
)

# If the extracted word count is below this threshold *and* an SPA marker is
# present, assume the page requires JavaScript rendering to produce content.
_SPA_MIN_WORDS = 20


def detect_platform(html: str, word_count: int) -> PlatformType:
    """Classify the platform/technology type of a web page.

    Args:
        html: Raw HTML string returned by the HTTP fetcher.
        word_count: Number of words extracted from the page by the extractor.

    Returns:
        A :data:`PlatformType` string identifying the detected platform.
    """
    if _WP_PATTERN.search(html):
        return "wordpress"

    # A page is treated as a SPA only when *both* conditions are met:
    # 1. An SPA framework fingerprint is present in the raw HTML shell.
    # 2. Very little readable content was extracted via plain HTTP — a sign
    #    that content is rendered client-side and was not sent by the server.
    if word_count < _SPA_MIN_WORDS and _SPA_PATTERN.search(html):
        return "spa"

    return "ssr"
