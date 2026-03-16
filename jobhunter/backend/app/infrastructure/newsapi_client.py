import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

NEWSAPI_BASE_URL = "https://newsapi.org/v2"


class NewsAPIClient:
    def __init__(self):
        self._api_key = settings.NEWSAPI_KEY
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search_articles(
        self,
        query: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int = 100,
        language: str = "en",
    ) -> list[dict]:
        """Search NewsAPI /v2/everything. Returns [] on error (soft failure)."""
        params = {
            "q": query,
            "apiKey": self._api_key,
            "pageSize": page_size,
            "language": language,
            "sortBy": "publishedAt",
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            resp = await self._client.get(f"{NEWSAPI_BASE_URL}/everything", params=params)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            logger.info("newsapi_search_done", query=query, total=data.get("totalResults", 0), returned=len(articles))
            return articles
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.error(
                    "newsapi_auth_error", status=e.response.status_code, detail="API key may be invalid or expired"
                )
                raise
            logger.warning("newsapi_http_error", status=e.response.status_code, query=query)
            return []
        except httpx.RequestError as e:
            logger.error("newsapi_request_error", error=str(e), query=query)
            return []
