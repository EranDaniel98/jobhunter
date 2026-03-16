"""Unit tests for app/infrastructure/newsapi_client.py."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.infrastructure.newsapi_client import NEWSAPI_BASE_URL, NewsAPIClient


def _make_response(status_code: int, body: dict | None = None) -> httpx.Response:
    content = json.dumps(body or {}).encode()
    return httpx.Response(
        status_code,
        content=content,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", f"{NEWSAPI_BASE_URL}/everything"),
    )


class TestNewsAPIClientSearchArticles:
    @pytest.mark.asyncio
    async def test_search_articles_success(self):
        """Returns parsed articles on a successful 200 response."""
        articles = [{"title": "AI News", "url": "https://example.com/1"}]
        mock_resp = _make_response(200, {"articles": articles, "totalResults": 1})
        mock_get = AsyncMock(return_value=mock_resp)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            result = await client.search_articles("AI funding")

        assert result == articles
        mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_articles_empty(self):
        """Returns empty list when API returns empty articles array."""
        mock_resp = _make_response(200, {"articles": [], "totalResults": 0})
        mock_get = AsyncMock(return_value=mock_resp)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            result = await client.search_articles("obscure query")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_articles_with_dates(self):
        """from_date and to_date are passed as query params."""
        mock_resp = _make_response(200, {"articles": [], "totalResults": 0})
        mock_get = AsyncMock(return_value=mock_resp)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            await client.search_articles("startup", from_date="2024-01-01", to_date="2024-01-31")

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs["params"]
        assert params["from"] == "2024-01-01"
        assert params["to"] == "2024-01-31"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_search_articles_auth_error_raises(self, status_code: int):
        """401/403 responses raise HTTPStatusError (not swallowed)."""
        resp = _make_response(status_code, {"message": "Unauthorized"})
        error = httpx.HTTPStatusError("auth error", request=resp.request, response=resp)
        mock_get = AsyncMock(side_effect=error)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get), pytest.raises(httpx.HTTPStatusError):
            await client.search_articles("query")

    @pytest.mark.asyncio
    async def test_search_articles_server_error_returns_empty(self):
        """500 server error returns [] instead of raising."""
        resp = _make_response(500, {"message": "Internal Server Error"})
        error = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        mock_get = AsyncMock(side_effect=error)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            result = await client.search_articles("query")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_articles_network_error_returns_empty(self):
        """ConnectError (network failure) returns [] gracefully."""
        mock_get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            result = await client.search_articles("query")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_articles_missing_articles_key(self):
        """If response body has no 'articles' key, returns []."""
        mock_resp = _make_response(200, {"status": "ok"})
        mock_get = AsyncMock(return_value=mock_resp)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            result = await client.search_articles("query")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_articles_default_params(self):
        """Default parameters are passed correctly."""
        mock_resp = _make_response(200, {"articles": [], "totalResults": 0})
        mock_get = AsyncMock(return_value=mock_resp)

        client = NewsAPIClient()
        with patch.object(client._client, "get", mock_get):
            await client.search_articles("test query")

        call_kwargs = mock_get.call_args[1]
        params = call_kwargs["params"]
        assert params["q"] == "test query"
        assert params["pageSize"] == 100
        assert params["language"] == "en"
        assert params["sortBy"] == "publishedAt"
        assert "from" not in params
        assert "to" not in params
