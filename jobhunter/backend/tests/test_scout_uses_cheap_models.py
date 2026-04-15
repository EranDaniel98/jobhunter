"""Verify scout pipeline routes query-gen + article-parse LLM calls to the cheap model."""
import pytest

import app.dependencies as deps
from app.config import settings


class _CapturingOpenAI:
    def __init__(self):
        self.calls: list[dict] = []

    async def parse_structured(self, system_prompt, user_content, schema, **kwargs):
        self.calls.append(kwargs)
        # Return schema-appropriate shape for parse_articles path
        if "companies" in (schema.get("properties") or {}):
            return {"companies": []}
        if "queries" in (schema.get("properties") or {}):
            return {"queries": ["q1", "q2"]}
        return {}


@pytest.mark.asyncio
async def test_parse_articles_uses_cheap_model(monkeypatch):
    from app.graphs.scout_pipeline import parse_articles_node

    fake = _CapturingOpenAI()
    monkeypatch.setattr(deps, "_openai_client", fake)

    state = {
        "raw_articles": [
            {
                "title": "t",
                "description": "d",
                "url": "u",
                "source": {"name": "s"},
                "publishedAt": "2026-01-01T00:00:00Z",
            }
        ]
    }
    await parse_articles_node(state)

    assert len(fake.calls) == 1
    assert fake.calls[0].get("model") == settings.SCOUT_PARSE_MODEL
