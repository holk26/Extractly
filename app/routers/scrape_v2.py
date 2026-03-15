"""V2 scrape endpoint – enqueues a background Inngest job instead of
processing the request synchronously.

The endpoint accepts the same body as ``POST /v1/scrape`` and immediately
returns a job ID.  The actual scraping is handled asynchronously by the
``extractly/scrape.requested`` Inngest function defined in
``app/inngest_client.py``.
"""

import logging

import inngest
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import require_auth
from app.inngest_client import inngest_client
from app.models.request import ScrapeRequest

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post(
    "/scrape",
    summary="Async scrape (Inngest-backed)",
    description=(
        "Enqueues a background scrape job via Inngest and returns the "
        "event/job ID immediately.  The scraping happens asynchronously; "
        "use the Inngest dashboard to inspect the result."
    ),
)
async def scrape_async(body: ScrapeRequest) -> dict:
    """Send a ``extractly/scrape.requested`` event to Inngest."""
    url = str(body.url)
    logger.info("V2 async scrape request received", extra={"url": url})

    try:
        ids = await inngest_client.send(
            inngest.Event(
                name="extractly/scrape.requested",
                data={"url": url, "render_mode": body.render_mode},
            )
        )
    except Exception as exc:
        logger.error("Failed to enqueue scrape job for %s: %s", url, exc)
        raise HTTPException(status_code=502, detail="Failed to enqueue scrape job.")

    event_id = ids[0] if ids else ""
    return {"status": "queued", "event_id": event_id, "url": url}
