import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB
TIMEOUT = 10  # seconds
MAX_REDIRECTS = 10
ALLOWED_SCHEMES = {"http", "https"}


def _is_private_address(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private, loopback, or link-local address."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        raw_ip = info[4][0]
        # Strip IPv6 zone IDs (e.g. "::1%eth0" → "::1")
        raw_ip = raw_ip.split("%")[0]
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return True
    return False


def _validate_url(url: str) -> None:
    """Raise ValueError if *url* fails SSRF / scheme validation."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' is not allowed. Use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname.")

    if _is_private_address(hostname):
        raise ValueError("Requests to private/internal addresses are not allowed.")


async def fetch_url(url: str) -> str:
    """Fetch *url* and return the response body as a string.

    Redirects are followed manually so that every redirect destination is
    validated against the SSRF rules before the next request is made.

    Raises:
        ValueError: if the URL fails SSRF / scheme validation.
        httpx.HTTPError: on network or HTTP errors.
        RuntimeError: if the response body exceeds MAX_CONTENT_SIZE.
    """
    _validate_url(url)

    current_url = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    next_url = urljoin(current_url, location)
                    _validate_url(next_url)
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

