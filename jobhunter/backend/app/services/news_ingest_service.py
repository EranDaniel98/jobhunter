"""Global daily NewsAPI ingest — writes to funding_signals for shared consumption."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.protocols import NewsAPIClientProtocol, OpenAIClientProtocol
from app.models.funding_signal import FundingSignal

logger = structlog.get_logger()


DEFAULT_QUERIES: list[str] = [
    "Series A funding announcement",
    "Series B funding round",
    "startup raised seed round hiring",
]

PARSE_ARTICLES_PROMPT = (
    "You extract structured funding data from recent news.\n"
    "For each article, return the funded company (name, estimated domain, funding"
    " round, amount, industry, 1-sentence description, and the original URL).\n"
    "Articles:\n"
    "{articles_block}\n"
)

PARSE_ARTICLES_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "estimated_domain": {"type": ["string", "null"]},
                    "funding_round": {"type": ["string", "null"]},
                    "amount": {"type": ["string", "null"]},
                    "industry": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "source_url": {"type": "string"},
                },
                "required": [
                    "company_name",
                    "estimated_domain",
                    "funding_round",
                    "amount",
                    "industry",
                    "description",
                    "source_url",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["companies"],
    "additionalProperties": False,
}


async def ingest_funding_news(
    db: AsyncSession,
    news: NewsAPIClientProtocol,
    openai: OpenAIClientProtocol,
    *,
    queries: list[str] | None = None,
    lookback_days: int = 7,
    expires_days: int = 30,
) -> int:
    """Fetch funding news, parse, dedupe-by-URL, store to funding_signals with
    embeddings. Returns count of new rows inserted."""
    queries = queries or DEFAULT_QUERIES
    from_date = (datetime.now(UTC) - timedelta(days=lookback_days)).date().isoformat()
    to_date = datetime.now(UTC).date().isoformat()

    # 1. Fetch from NewsAPI (soft-fail per query)
    articles: list[dict] = []
    for q in queries:
        try:
            batch = await news.search_articles(q, from_date=from_date, to_date=to_date, page_size=50)
            articles.extend(batch)
        except Exception as e:
            logger.warning("news_ingest.newsapi_error", query=q, error=str(e))
            continue

    if not articles:
        logger.info("news_ingest.no_articles")
        return 0

    # 2. Dedupe by URL within this batch + against existing DB rows
    seen_urls = {a.get("url") for a in articles if a.get("url")}
    existing = set(
        (await db.execute(select(FundingSignal.source_url).where(FundingSignal.source_url.in_(seen_urls))))
        .scalars()
        .all()
    )
    new_articles = [a for a in articles if a.get("url") and a["url"] not in existing]

    if not new_articles:
        logger.info("news_ingest.all_duplicates", total=len(articles))
        return 0

    # 3. LLM parse (cheap model)
    articles_block = "\n".join(
        f"- {a.get('title', '')} | {a.get('description', '')} | URL: {a.get('url')}" for a in new_articles[:50]
    )
    try:
        parsed = await openai.parse_structured(
            PARSE_ARTICLES_PROMPT.format(articles_block=articles_block),
            "",
            PARSE_ARTICLES_SCHEMA,
            model=settings.SCOUT_PARSE_MODEL,
        )
    except Exception as e:
        logger.error("news_ingest.parse_failed", error=str(e))
        return 0

    now = datetime.now(UTC)
    expires = now + timedelta(days=expires_days)
    inserted = 0

    article_by_url = {a.get("url"): a for a in new_articles}

    for c in parsed.get("companies", []):
        url = c.get("source_url")
        if not url or url in existing:
            continue

        source_article = article_by_url.get(url, {})
        embed_text_input = f"{c.get('company_name', '')} {c.get('description', '')} {c.get('industry', '')}".strip()
        try:
            embedding = await openai.embed(embed_text_input, dimensions=1536)
        except Exception as e:
            logger.warning("news_ingest.embed_failed", url=url, error=str(e))
            embedding = None

        sig = FundingSignal(
            id=uuid4(),
            source_url=url,
            title=(source_article.get("title") or c.get("company_name", ""))[:500],
            description=c.get("description") or source_article.get("description"),
            published_at=_parse_published(source_article.get("publishedAt")) or now,
            source_name=(source_article.get("source") or {}).get("name"),
            company_name=c.get("company_name"),
            estimated_domain=c.get("estimated_domain"),
            funding_round=c.get("funding_round"),
            amount=c.get("amount"),
            industry=c.get("industry"),
            signal_types=["funding_round"],
            extra_data={
                "funding_round": c.get("funding_round"),
                "amount": c.get("amount"),
            },
            embedding=embedding,
            parsed_at=now,
            expires_at=expires,
        )
        db.add(sig)
        inserted += 1

    await db.commit()
    logger.info("news_ingest.completed", fetched=len(articles), new=inserted)
    return inserted


def _parse_published(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
