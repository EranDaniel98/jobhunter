import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger()

JINA_READER_BASE = "https://r.jina.ai"
TIMEOUT = 20.0  # Jina needs time to render JS


async def _validate_url(url: str) -> None:
    parsed = urlparse(str(url))
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP/HTTPS URLs are allowed")
    hostname = parsed.hostname or ""
    try:
        loop = asyncio.get_running_loop()
        resolved = await loop.run_in_executor(None, socket.gethostbyname, hostname)
        ip = ipaddress.ip_address(resolved)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("Internal/private URLs are not allowed")
    except socket.gaierror:
        logger.warning("url_validation_dns_failed", url=url)


async def scrape_job_url(url: str) -> str:
    """Fetch a job posting URL via Jina Reader API and return clean markdown text."""
    await _validate_url(url)
    jina_url = f"{JINA_READER_BASE}/{url}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            jina_url,
            headers={"Accept": "text/markdown"},
            follow_redirects=True,
        )
        response.raise_for_status()

    text = response.text.strip()
    if not text:
        raise ValueError("Scraping returned empty content for URL")

    logger.info("url_scraped", url=url, length=len(text))
    return text
