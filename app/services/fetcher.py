from urllib.parse import urljoin

import httpx

from app.services.url_utils import (
    MAX_CONTENT_SIZE,
    validate_url,
)

TIMEOUT = 10  # seconds
MAX_REDIRECTS = 10


async def fetch_url(url: str) -> str:
    """Fetch *url* and return the response body as a string.

    Redirects are followed manually so that every redirect destination is
    validated against the SSRF rules before the next request is made.

    Raises:
        ValueError: if the URL fails SSRF / scheme validation.
        httpx.HTTPError: on network or HTTP errors.
        RuntimeError: if the response body exceeds MAX_CONTENT_SIZE.
    """
    validate_url(url)

    current_url = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    next_url = urljoin(current_url, location)
                    validate_url(next_url)
                    current_url = next_url
                    continue

                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_CONTENT_SIZE:
                    raise RuntimeError("Response body exceeds the maximum allowed size.")

                chunks = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_CONTENT_SIZE:
                        raise RuntimeError("Response body exceeds the maximum allowed size.")
                    chunks.append(chunk)

                return b"".join(chunks).decode(errors="replace")

    raise RuntimeError("Too many redirects.")

