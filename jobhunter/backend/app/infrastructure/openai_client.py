import base64
import json

import structlog
from openai import AsyncOpenAI

from app.config import settings
from app.services.cost_service import check_budget, record_usage
from app.utils.retry import retry_on_rate_limit

logger = structlog.get_logger()


class OpenAIClient:
    def __init__(self):
        import httpx as _httpx

        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=_httpx.Timeout(60.0, connect=10.0),
        )

    @retry_on_rate_limit
    async def parse_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_schema: dict,
        *,
        max_tokens: int = 4000,
        candidate_id: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
    ) -> dict:
        resolved_model = model or "gpt-4o"
        await check_budget()
        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": response_schema,
                    "strict": True,
                },
            },
        )
        if response.usage:
            await record_usage(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                candidate_id=candidate_id,
                endpoint=endpoint,
                model=resolved_model,
            )
        return json.loads(response.choices[0].message.content)

    @retry_on_rate_limit
    async def embed(self, text: str, dimensions: int = 1536) -> list[float]:
        await check_budget()
        response = await self._client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            dimensions=dimensions,
        )
        if response.usage:
            await record_usage(response.usage.prompt_tokens, 0, model="text-embedding-3-large")
        return response.data[0].embedding

    @retry_on_rate_limit
    async def batch_embed(self, texts: list[str], dimensions: int = 1536) -> list[list[float]]:
        await check_budget()
        response = await self._client.embeddings.create(
            model="text-embedding-3-large",
            input=texts,
            dimensions=dimensions,
        )
        if response.usage:
            await record_usage(response.usage.prompt_tokens, 0, model="text-embedding-3-large")
        return [item.embedding for item in response.data]

    @retry_on_rate_limit
    async def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 2000,
        candidate_id: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
    ) -> str:
        resolved_model = model or "gpt-4o"
        await check_budget()
        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        if response.usage:
            await record_usage(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                candidate_id=candidate_id,
                endpoint=endpoint,
                model=resolved_model,
            )
        return response.choices[0].message.content

    @retry_on_rate_limit
    async def vision(
        self,
        messages: list[dict],
        images: list[bytes],
        *,
        max_tokens: int = 2000,
        candidate_id: str | None = None,
        endpoint: str | None = None,
    ) -> str:
        await check_budget()
        content = []
        for img in images:
            b64 = base64.b64encode(img).decode()
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
        for msg in messages:
            if msg.get("role") == "user":
                content.append({"type": "text", "text": msg["content"]})

        response = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
        )
        if response.usage:
            await record_usage(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                candidate_id=candidate_id,
                endpoint=endpoint,
                model="gpt-4o",
            )
        return response.choices[0].message.content
