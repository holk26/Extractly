import logging
import logging.config
import os

import inngest.fast_api
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.inngest_client import INNGEST_FUNCTIONS, inngest_client
from app.routers.crawl import router as crawl_router
from app.routers.extract import router as extract_router
from app.routers.extract_site import router as extract_site_router
from app.routers.health import router as health_router
from app.routers.performance import router as performance_router
from app.routers.playground import router as playground_router
from app.routers.scrape import limiter, router as scrape_router
from app.routers.scrape_v2 import router as scrape_v2_router


logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Extractly – Clean Scraper API",
    description="Fetches a URL, cleans the HTML, and returns structured Markdown content.",
    version="1.0.0",
)

# Rate-limiting state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS – allow moonsbow.com and every subdomain (e.g. panel.app.moonsbow.com)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://moonsbow.com",
        "https://www.moonsbow.com",
    ],
    allow_origin_regex=r"https://.*\.moonsbow\.com$",
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


app.include_router(scrape_router, prefix="/v1")
app.include_router(crawl_router, prefix="/v1")
app.include_router(extract_router, prefix="/v1")
app.include_router(extract_site_router, prefix="/v1")
app.include_router(playground_router, prefix="/v1")
app.include_router(health_router)
app.include_router(performance_router, prefix="/v1")
app.include_router(scrape_v2_router, prefix="/v2")

# Inngest endpoint – handles function registration and invocations.
# Served at /api/inngest when either INNGEST_DEV=1 (dev mode) or
# INNGEST_SIGNING_KEY is configured (production mode).
if os.getenv("INNGEST_DEV") == "1" or os.getenv("INNGEST_SIGNING_KEY"):
    inngest.fast_api.serve(app, inngest_client, INNGEST_FUNCTIONS)
else:
    logger.warning(
        "Inngest endpoint not registered: set INNGEST_DEV=1 for dev mode "
        "or INNGEST_SIGNING_KEY for production mode."
    )


@app.get("/", summary="API root")
async def root() -> dict:
    return {"message": "Hello from Extractly"}
