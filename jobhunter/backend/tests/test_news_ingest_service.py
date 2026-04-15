"""Verify the shared news ingest service: fetch → dedupe → parse → embed → upsert."""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.funding_signal import FundingSignal
from app.services import news_ingest_service


@pytest.mark.asyncio
async def test_ingest_creates_funding_signals(db_session):
    news = AsyncMock()
    news.search_articles = AsyncMock(return_value=[
        {
            "title": "Acme raised $10M Series A",
            "description": "Acme is a fintech.",
            "url": f"https://example.com/acme-{uuid.uuid4()}",
            "source": {"name": "TechCrunch"},
            "publishedAt": "2026-04-14T10:00:00Z",
        }
    ])
    article_url = news.search_articles.return_value[0]["url"]

    openai = AsyncMock()
    openai.parse_structured = AsyncMock(return_value={
        "companies": [
            {
                "company_name": "Acme",
                "estimated_domain": "acme.co",
                "funding_round": "Series A",
                "amount": "$10M",
                "industry": "fintech",
                "description": "Fintech",
                "source_url": article_url,
            }
        ]
    })
    openai.embed = AsyncMock(return_value=[0.1] * 1536)

    count = await news_ingest_service.ingest_funding_news(db_session, news, openai)

    assert count == 1
    sig = (
        await db_session.execute(
            select(FundingSignal).where(FundingSignal.source_url == article_url)
        )
    ).scalar_one()
    assert sig.company_name == "Acme"
    assert sig.embedding is not None
    assert len(sig.embedding) == 1536


@pytest.mark.asyncio
async def test_ingest_deduplicates_on_reruns(db_session):
    dup_url = f"https://dup.example/{uuid.uuid4()}"

    def _news_factory():
        n = AsyncMock()
        n.search_articles = AsyncMock(return_value=[
            {
                "title": "t",
                "description": "d",
                "url": dup_url,
                "source": {"name": "s"},
                "publishedAt": "2026-04-14T10:00:00Z",
            }
        ])
        return n

    openai = AsyncMock()
    openai.parse_structured = AsyncMock(return_value={
        "companies": [{
            "company_name": "X",
            "estimated_domain": "x.co",
            "funding_round": "Seed",
            "amount": "$1M",
            "industry": "ai",
            "description": "d",
            "source_url": dup_url,
        }]
    })
    openai.embed = AsyncMock(return_value=[0.1] * 1536)

    c1 = await news_ingest_service.ingest_funding_news(db_session, _news_factory(), openai)
    c2 = await news_ingest_service.ingest_funding_news(db_session, _news_factory(), openai)

    assert c1 == 1
    assert c2 == 0  # No duplicates inserted

    total = (
        await db_session.execute(
            select(FundingSignal).where(FundingSignal.source_url == dup_url)
        )
    ).scalars().all()
    assert len(total) == 1


@pytest.mark.asyncio
async def test_ingest_soft_fails_on_newsapi_error(db_session):
    news = AsyncMock()
    news.search_articles = AsyncMock(side_effect=Exception("boom"))
    openai = AsyncMock()

    count = await news_ingest_service.ingest_funding_news(db_session, news, openai)
    assert count == 0  # No crash, returns 0


@pytest.mark.asyncio
async def test_ingest_uses_cheap_parse_model(db_session, monkeypatch):
    """The LLM parse call should use SCOUT_PARSE_MODEL, not the default."""
    from app.config import settings

    url = f"https://example.com/cheap-{uuid.uuid4()}"
    news = AsyncMock()
    news.search_articles = AsyncMock(return_value=[{
        "title": "t", "description": "d", "url": url,
        "source": {"name": "s"}, "publishedAt": "2026-04-14T10:00:00Z",
    }])

    captured: dict = {}
    openai = AsyncMock()

    async def fake_parse(system_prompt, user_content, schema, **kwargs):
        captured.update(kwargs)
        return {"companies": []}

    openai.parse_structured = fake_parse
    openai.embed = AsyncMock(return_value=[0.1] * 1536)

    await news_ingest_service.ingest_funding_news(db_session, news, openai)
    assert captured.get("model") == settings.SCOUT_PARSE_MODEL
