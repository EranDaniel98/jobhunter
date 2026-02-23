import numpy as np
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
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))
