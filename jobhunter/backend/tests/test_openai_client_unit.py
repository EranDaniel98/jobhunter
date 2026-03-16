"""Unit tests for app/infrastructure/openai_client.py."""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.openai_client import OpenAIClient


def _make_chat_response(content: str, prompt_tokens: int = 100, completion_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_embedding_response(embeddings: list[list[float]], prompt_tokens: int = 20) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens

    items = []
    for emb in embeddings:
        item = MagicMock()
        item.embedding = emb
        items.append(item)

    response = MagicMock()
    response.data = items
    response.usage = usage
    return response


class TestParseStructured:
    @pytest.mark.asyncio
    async def test_parse_structured_success(self):
        """Returns parsed JSON from the model response."""
        expected = {"name": "Alice", "skills": ["Python"]}
        mock_response = _make_chat_response(json.dumps(expected))

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            result = await client.parse_structured(
                system_prompt="You are a parser.",
                user_content="Parse this.",
                response_schema={"type": "object"},
            )

        assert result == expected

    @pytest.mark.asyncio
    async def test_parse_structured_records_usage(self):
        """record_usage is called with correct prompt/completion token counts."""
        mock_response = _make_chat_response(json.dumps({"key": "val"}), prompt_tokens=200, completion_tokens=75)
        mock_record = AsyncMock()

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", mock_record),
        ):
            await client.parse_structured("sys", "user", {}, candidate_id="cid-1", endpoint="/test")

        mock_record.assert_awaited_once()
        call_args = mock_record.call_args
        assert call_args[0][0] == 200  # prompt_tokens
        assert call_args[0][1] == 75  # completion_tokens
        assert call_args[1]["candidate_id"] == "cid-1"
        assert call_args[1]["endpoint"] == "/test"
        assert call_args[1]["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_parse_structured_no_usage(self):
        """record_usage is NOT called when response.usage is None."""
        mock_response = _make_chat_response(json.dumps({"key": "val"}))
        mock_response.usage = None
        mock_record = AsyncMock()

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", mock_record),
        ):
            await client.parse_structured("sys", "user", {})

        mock_record.assert_not_awaited()


class TestEmbed:
    @pytest.mark.asyncio
    async def test_embed_success(self):
        """Returns a flat list of floats for a single text input."""
        embedding = [0.1, 0.2, 0.3]
        mock_response = _make_embedding_response([embedding])

        client = OpenAIClient()
        with (
            patch.object(client._client.embeddings, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            result = await client.embed("hello world")

        assert result == embedding

    @pytest.mark.asyncio
    async def test_batch_embed_success(self):
        """Returns list of embeddings for multiple inputs."""
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        mock_response = _make_embedding_response(embeddings)

        client = OpenAIClient()
        with (
            patch.object(client._client.embeddings, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            result = await client.batch_embed(["text one", "text two"])

        assert result == embeddings
        assert len(result) == 2


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Returns the message content string."""
        mock_response = _make_chat_response("Hello, I can help!")

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            result = await client.chat([{"role": "user", "content": "Hello"}])

        assert result == "Hello, I can help!"

    @pytest.mark.asyncio
    async def test_chat_records_usage(self):
        """Usage is recorded with correct token counts and metadata."""
        mock_response = _make_chat_response("answer", prompt_tokens=150, completion_tokens=30)
        mock_record = AsyncMock()

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", mock_record),
        ):
            await client.chat(
                [{"role": "user", "content": "q"}],
                candidate_id="cid-2",
                endpoint="/chat",
            )

        mock_record.assert_awaited_once()
        call_args = mock_record.call_args
        assert call_args[0][0] == 150
        assert call_args[0][1] == 30
        assert call_args[1]["candidate_id"] == "cid-2"
        assert call_args[1]["endpoint"] == "/chat"

    @pytest.mark.asyncio
    async def test_chat_no_usage_not_recorded(self):
        """record_usage is NOT called when response.usage is None."""
        mock_response = _make_chat_response("answer")
        mock_response.usage = None
        mock_record = AsyncMock()

        client = OpenAIClient()
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", mock_record),
        ):
            await client.chat([{"role": "user", "content": "q"}])

        mock_record.assert_not_awaited()


class TestVision:
    @pytest.mark.asyncio
    async def test_vision_success(self):
        """Returns the content string from the vision response."""
        mock_response = _make_chat_response("I see a chart.")

        client = OpenAIClient()
        image_bytes = b"fake-image-data"
        with (
            patch.object(client._client.chat.completions, "create", AsyncMock(return_value=mock_response)),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            result = await client.vision(
                messages=[{"role": "user", "content": "Describe this image"}],
                images=[image_bytes],
            )

        assert result == "I see a chart."

    @pytest.mark.asyncio
    async def test_vision_builds_correct_content(self):
        """Images are base64-encoded and user messages are extracted into content list."""
        mock_response = _make_chat_response("description")
        captured_call = {}

        async def capture_create(*args, **kwargs):
            captured_call.update(kwargs)
            return mock_response

        client = OpenAIClient()
        image_bytes = b"\x89PNG\r\n"
        with (
            patch.object(client._client.chat.completions, "create", capture_create),
            patch("app.infrastructure.openai_client.check_budget", AsyncMock()),
            patch("app.infrastructure.openai_client.record_usage", AsyncMock()),
        ):
            await client.vision(
                messages=[{"role": "user", "content": "What is this?"}],
                images=[image_bytes],
            )

        messages_sent = captured_call["messages"]
        assert len(messages_sent) == 1
        content = messages_sent[0]["content"]

        # Should have image_url entry
        image_entries = [c for c in content if c.get("type") == "image_url"]
        assert len(image_entries) == 1
        expected_b64 = base64.b64encode(image_bytes).decode()
        assert image_entries[0]["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"

        # Should have text entry from user message
        text_entries = [c for c in content if c.get("type") == "text"]
        assert len(text_entries) == 1
        assert text_entries[0]["text"] == "What is this?"
