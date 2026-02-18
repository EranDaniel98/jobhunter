import math

import structlog

from app.dependencies import get_openai

logger = structlog.get_logger()


async def embed_text(text: str, dimensions: int = 1536) -> list[float]:
    client = get_openai()
    return await client.embed(text, dimensions=dimensions)


async def batch_embed(texts: list[str], dimensions: int = 1536) -> list[list[float]]:
    if not texts:
        return []
    client = get_openai()
    return await client.batch_embed(texts, dimensions=dimensions)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
