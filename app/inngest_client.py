"""Inngest client and background functions for Extractly.

This module sets up the Inngest client and defines background functions that
are triggered by events sent to the Inngest server.

The Inngest endpoint is served at ``/api/inngest`` by ``app/main.py``.

Environment variables
---------------------
INNGEST_DEV
    Set to ``1`` to run in dev mode (connects to the local Dev Server).
    Required when using the Inngest CLI Dev Server locally.
INNGEST_BASE_URL
    Base URL of a **self-hosted** Inngest server (both API calls and event
    delivery).  Example: ``http://inngest.internal:8288``.
    Takes precedence over the default Inngest Cloud endpoints.
    When ``INNGEST_DEV=1`` is also set, the SDK already defaults to
    ``http://127.0.0.1:8288``, so you only need this variable when your
    self-hosted server is on a different address.
INNGEST_EVENT_API_BASE_URL
    Override only the event-sending endpoint.  Useful when the event API is
    on a different host than the main API.
    If ``INNGEST_BASE_URL`` is set, this variable is ignored.
INNGEST_SIGNING_KEY
    Signing key used to verify that requests arriving at ``/api/inngest``
    were sent by your Inngest server.  Required in production mode.

Self-hosted quick start
-----------------------
Start your Inngest server (e.g. with Docker)::

    docker run -p 8288:8288 inngest/inngest \\
        inngest dev -u http://host.docker.internal:8000/api/inngest --no-discovery

Then start the app with the matching base URL::

    INNGEST_DEV=1 INNGEST_BASE_URL=http://localhost:8288 uvicorn main:app --reload

For a production self-hosted setup set ``INNGEST_BASE_URL`` and
``INNGEST_SIGNING_KEY`` instead of ``INNGEST_DEV``::

    INNGEST_BASE_URL=https://inngest.mycompany.com \\
    INNGEST_SIGNING_KEY=signkey-prod-... \\
    uvicorn main:app
"""

import logging
import os

import inngest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inngest client
# ---------------------------------------------------------------------------

# Optional self-hosted / custom server URLs read from the environment.
_base_url: str | None = os.getenv("INNGEST_BASE_URL") or None
_event_api_base_url: str | None = os.getenv("INNGEST_EVENT_API_BASE_URL") or None
_signing_key: str | None = os.getenv("INNGEST_SIGNING_KEY") or None

inngest_client = inngest.Inngest(
    app_id="extractly",
    logger=logging.getLogger("uvicorn"),
    is_production=os.getenv("INNGEST_DEV") != "1",
    # Self-hosted / custom server support.
    # api_base_url covers both the API and event delivery; if only the
    # event endpoint differs, event_api_base_url can be set independently.
    api_base_url=_base_url,
    event_api_base_url=_event_api_base_url if not _base_url else None,
    signing_key=_signing_key,
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
