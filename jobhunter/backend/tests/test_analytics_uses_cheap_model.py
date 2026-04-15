"""Verify analytics pipeline routes insight-generation LLM call to the cheap model."""
import pytest

import app.dependencies as deps
from app.config import settings


class _CapturingOpenAI:
    def __init__(self):
        self.calls: list[dict] = []

    async def parse_structured(self, system_prompt, user_content, schema, **kwargs):
        self.calls.append(kwargs)
        return {
            "insights": [
                {
                    "insight_type": "pipeline_health",
                    "title": "t",
                    "body": "b",
                    "severity": "info",
                    "data": {},
                }
            ]
        }


@pytest.mark.asyncio
async def test_generate_insights_uses_cheap_model(monkeypatch):
    from app.graphs.analytics_pipeline import generate_insights_node

    fake = _CapturingOpenAI()
    monkeypatch.setattr(deps, "_openai_client", fake)

    state = {
        "raw_data": {
            "pipeline": {},
            "funnel": {},
            "outreach": {},
            "skills": [],
            "skill_count": 0,
            "career_stage": "mid",
            "experience_summary": "eng",
        },
    }
    await generate_insights_node(state)

    assert len(fake.calls) == 1
    assert fake.calls[0].get("model") == settings.ANALYTICS_INSIGHTS_MODEL
