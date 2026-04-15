import pytest

from app.infrastructure import openai_client as openai_client_mod
from app.infrastructure.openai_client import OpenAIClient


async def _noop_check_budget():
    return None


async def _noop_record_usage(*args, **kwargs):
    return None


def _install_fakes(monkeypatch, captured: dict):
    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            class _Msg:
                content = '{"x": 1}'
            class _Choice:
                message = _Msg()
            class _Resp:
                choices = [_Choice()]
                usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1})()
            return _Resp()

    class FakeClient:
        chat = type("C", (), {"completions": FakeCompletions()})()

    client = OpenAIClient()
    monkeypatch.setattr(client, "_client", FakeClient())
    monkeypatch.setattr(openai_client_mod, "check_budget", _noop_check_budget)
    monkeypatch.setattr(openai_client_mod, "record_usage", _noop_record_usage)
    return client


@pytest.mark.asyncio
async def test_parse_structured_accepts_model_kwarg(monkeypatch):
    """Passing `model=` overrides the default gpt-4o."""
    captured: dict = {}
    client = _install_fakes(monkeypatch, captured)

    await client.parse_structured(
        "system", "user", {"type": "object", "properties": {"x": {"type": "integer"}}},
        model="gpt-4o-mini",
    )

    assert captured["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_parse_structured_defaults_to_gpt4o(monkeypatch):
    """When `model` is omitted, falls back to gpt-4o."""
    captured: dict = {}
    client = _install_fakes(monkeypatch, captured)

    await client.parse_structured("system", "user", {"type": "object"})

    assert captured["model"] == "gpt-4o"
