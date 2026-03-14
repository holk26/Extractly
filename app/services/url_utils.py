"""Shared URL validation and SSRF-protection utilities.

These helpers are used by every fetching module (fetcher, browser_fetcher,
site_crawler) so they live in one canonical place.  Importing from here keeps
security-critical logic in sync across the whole service.
"""

import ipaddress
import socket
from urllib.parse import urlparse

# Maximum response/rendered-page size that any fetcher will accept.
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB

# Playwright browser timeout (milliseconds)
BROWSER_TIMEOUT_MS = 30_000  # 30 s

# URL schemes permitted for all outbound requests
ALLOWED_SCHEMES = {"http", "https"}


def is_private_address(hostname: str) -> bool:
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


def validate_url(url: str) -> None:
    """Raise ValueError if *url* fails SSRF / scheme validation."""
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' is not allowed. Use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname.")

    if is_private_address(hostname):
        raise ValueError("Requests to private/internal addresses are not allowed.")
