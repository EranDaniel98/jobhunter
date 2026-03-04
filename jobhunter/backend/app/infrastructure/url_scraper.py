import httpx
import structlog

logger = structlog.get_logger()

JINA_READER_BASE = "https://r.jina.ai"
TIMEOUT = 20.0  # Jina needs time to render JS


async def scrape_job_url(url: str) -> str:
    """Fetch a job posting URL via Jina Reader API and return clean markdown text."""
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
