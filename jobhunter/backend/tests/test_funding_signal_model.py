"""Verify FundingSignal ORM + unique constraint on source_url."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.funding_signal import FundingSignal


@pytest.mark.asyncio
async def test_can_insert_and_fetch_funding_signal(db_session):
    sig = FundingSignal(
        id=uuid.uuid4(),
        source_url="https://example.com/article-1",
        title="Acme raised $10M Series A",
        description="Acme is a fintech.",
        published_at=datetime.now(UTC),
        source_name="NewsAPI",
        company_name="Acme",
        estimated_domain="acme.co",
        funding_round="Series A",
        amount="$10M",
        industry="fintech",
        signal_types=["funding_round"],
        extra_data={"funding_round": "Series A", "amount": "$10M"},
        embedding=[0.1] * 1536,
    )
    db_session.add(sig)
    await db_session.commit()

    fetched = (
        await db_session.execute(
            select(FundingSignal).where(FundingSignal.source_url == "https://example.com/article-1")
        )
    ).scalar_one()

    assert fetched.company_name == "Acme"
    assert fetched.signal_types == ["funding_round"]
    assert fetched.embedding is not None
    assert len(fetched.embedding) == 1536


@pytest.mark.asyncio
async def test_source_url_is_unique(db_session):
    url = f"https://dup.example/{uuid.uuid4()}"
    s1 = FundingSignal(
        id=uuid.uuid4(),
        source_url=url,
        title="t1",
        published_at=datetime.now(UTC),
    )
    db_session.add(s1)
    await db_session.commit()

    s2 = FundingSignal(
        id=uuid.uuid4(),
        source_url=url,
        title="t2",
        published_at=datetime.now(UTC),
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
