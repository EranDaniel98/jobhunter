import httpx
import structlog

from app.config import settings
from app.infrastructure.redis_client import get_redis
from app.utils.retry import retry_on_rate_limit

logger = structlog.get_logger()

HUNTER_BASE_URL = "https://api.hunter.io/v2"
CIRCUIT_BREAKER_KEY = "hunter:circuit_breaker"
RATE_LIMIT_KEY = "hunter:rate_limit"


class HunterClient:
    def __init__(self):
        self._api_key = settings.HUNTER_API_KEY
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _check_circuit_breaker(self) -> None:
        redis = get_redis()
        if await redis.get(f"{CIRCUIT_BREAKER_KEY}:open"):
            raise RuntimeError("Hunter.io circuit breaker is open")

    async def _record_failure(self) -> None:
        redis = get_redis()
        failures = await redis.incr(f"{CIRCUIT_BREAKER_KEY}:failures")
        await redis.expire(f"{CIRCUIT_BREAKER_KEY}:failures", 60)
        if failures >= 5:
            await redis.setex(f"{CIRCUIT_BREAKER_KEY}:open", 60, "1")
            logger.warning("hunter_circuit_breaker_opened")

    async def _record_success(self) -> None:
        redis = get_redis()
        await redis.delete(f"{CIRCUIT_BREAKER_KEY}:failures")

    async def _rate_limit(self, limit: int = 15) -> None:
        redis = get_redis()
        current = await redis.incr(RATE_LIMIT_KEY)
        if current == 1:
            await redis.expire(RATE_LIMIT_KEY, 1)
        if current > limit:
            await __import__("asyncio").sleep(1)

    async def _request(self, endpoint: str, params: dict | None = None) -> dict:
        await self._check_circuit_breaker()
        await self._rate_limit()

        url = f"{HUNTER_BASE_URL}/{endpoint}"
        all_params = {"api_key": self._api_key, **(params or {})}

        try:
            resp = await self._client.get(url, params=all_params)
            resp.raise_for_status()
            await self._record_success()
            return resp.json().get("data", resp.json())
        except httpx.HTTPStatusError as e:
            await self._record_failure()
            logger.error("hunter_api_error", status=e.response.status_code, endpoint=endpoint)
            raise
        except httpx.RequestError as e:
            await self._record_failure()
            logger.error("hunter_request_error", error=str(e), endpoint=endpoint)
            raise

    @retry_on_rate_limit
    async def domain_search(self, domain: str) -> dict:
        return await self._request("domain-search", {"domain": domain})

    @retry_on_rate_limit
    async def email_finder(self, domain: str, first_name: str, last_name: str) -> dict:
        return await self._request(
            "email-finder",
            {"domain": domain, "first_name": first_name, "last_name": last_name},
        )

    @retry_on_rate_limit
    async def email_verifier(self, email: str) -> dict:
        return await self._request("email-verifier", {"email": email})

    @retry_on_rate_limit
    async def enrichment(self, email: str) -> dict:
        return await self._request("people/email", {"email": email})
