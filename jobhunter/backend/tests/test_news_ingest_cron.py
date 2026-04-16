"""Verify the run_daily_news_ingest cron coordinator + registration."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_news_ingest_cron_calls_service(monkeypatch):
    from app import worker

    called: dict = {}

    async def fake_ingest(db, news, openai, **kwargs):
        called["ok"] = True
        return 3

    monkeypatch.setattr("app.services.news_ingest_service.ingest_funding_news", fake_ingest)
    monkeypatch.setattr(worker, "_acquire_run_lock", AsyncMock(return_value=True))

    await worker.run_daily_news_ingest({})

    assert called.get("ok") is True


@pytest.mark.asyncio
async def test_news_ingest_cron_respects_lock(monkeypatch):
    from app import worker

    called: dict = {"ingest": False}

    async def fake_ingest(db, news, openai, **kwargs):
        called["ingest"] = True
        return 0

    monkeypatch.setattr("app.services.news_ingest_service.ingest_funding_news", fake_ingest)
    monkeypatch.setattr(worker, "_acquire_run_lock", AsyncMock(return_value=False))

    await worker.run_daily_news_ingest({})
    assert called["ingest"] is False


def test_news_ingest_cron_is_registered():
    from app.worker import WorkerSettings

    cron_names = [c.coroutine.__name__ for c in WorkerSettings.cron_jobs]
    assert "run_daily_news_ingest" in cron_names
