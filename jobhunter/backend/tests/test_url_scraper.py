import pytest
import httpx

from app.infrastructure.url_scraper import scrape_job_url


class TestScrapeJobUrl:
    @pytest.mark.asyncio
    async def test_returns_markdown_on_success(self, monkeypatch):
        fake_markdown = "# Senior Engineer\n\nWe are looking for..."

        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, text=fake_markdown, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await scrape_job_url("https://example.com/jobs/123")
        assert "Senior Engineer" in result
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            resp = httpx.Response(403, text="Forbidden", request=httpx.Request("GET", url))
            resp.raise_for_status()
            return resp  # pragma: no cover

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        with pytest.raises(httpx.HTTPStatusError):
            await scrape_job_url("https://blocked.com/job")

    @pytest.mark.asyncio
    async def test_raises_on_empty_response(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, text="", request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        with pytest.raises(ValueError, match="empty"):
            await scrape_job_url("https://example.com/empty")
