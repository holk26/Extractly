import logging
import logging.config

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.routers.crawl import router as crawl_router
from app.routers.extract import router as extract_router
from app.routers.playground import router as playground_router
from app.routers.scrape import limiter, router as scrape_router

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


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception for %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


app.include_router(scrape_router)
app.include_router(crawl_router)
app.include_router(extract_router)
app.include_router(playground_router)


@app.get("/", summary="Health check")
async def root() -> dict:
    return {"message": "Hello from Extractly"}
