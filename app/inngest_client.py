"""Inngest client and background functions for Extractly.

This module sets up the Inngest client and defines background functions that
are triggered by events sent to the Inngest server.

The Inngest endpoint is served at ``/api/inngest`` by ``app/main.py``.

To use the Dev Server locally, start the app with ``INNGEST_DEV=1`` and run::

    npx --ignore-scripts=false inngest-cli@latest dev \\
        -u http://127.0.0.1:8000/api/inngest --no-discovery
"""

import logging
import os

import inngest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inngest client
# ---------------------------------------------------------------------------

inngest_client = inngest.Inngest(
    app_id="extractly",
    logger=logging.getLogger("uvicorn"),
    is_production=os.getenv("INNGEST_DEV") != "1",
)

# ---------------------------------------------------------------------------
# Background functions
# ---------------------------------------------------------------------------


@inngest_client.create_function(
    fn_id="scrape_page",
    trigger=inngest.TriggerEvent(event="extractly/scrape.requested"),
)
async def fn_scrape_page(ctx: inngest.Context, step: inngest.Step) -> dict:
    """Background scrape function triggered by the ``extractly/scrape.requested`` event.

    Expected event data keys:
    - ``url`` (str): The URL to scrape.
    - ``render_mode`` (str, optional): ``"auto"``, ``"http"``, or ``"browser"``.
      Defaults to ``"auto"``.

    Returns a dict with ``url``, ``title``, ``word_count``, and
    ``platform_type``.
    """
    url: str = ctx.event.data.get("url", "")
    render_mode: str = ctx.event.data.get("render_mode", "auto")

    ctx.logger.info("Inngest scrape_page started", extra={"url": url})

    async def _fetch() -> str:
        if render_mode == "browser":
            from app.services.fetching.browser_fetcher import fetch_url_with_browser

            return await fetch_url_with_browser(url)
        from app.services.fetching.fetcher import fetch_url

        return await fetch_url(url)

    html: str = await step.run("fetch_html", _fetch)

    async def _extract() -> dict:
        from app.services.parsing.extractor import extract
        from app.services.platforms.detector import detect_platform

        title, _desc, _md, _imgs, _vids, _links, word_count = extract(html, url)
        platform_type = detect_platform(html, word_count)
        return {"title": title, "word_count": word_count, "platform_type": platform_type}

    result: dict = await step.run("extract_content", _extract)

    return {"url": url, **result}


# ---------------------------------------------------------------------------
# Exported list of all registered functions (used by main.py)
# ---------------------------------------------------------------------------

INNGEST_FUNCTIONS: list[inngest.Function] = [fn_scrape_page]
