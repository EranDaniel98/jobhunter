import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def _is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    try:
        from openai import RateLimitError

        return isinstance(exc, RateLimitError)
    except ImportError:
        pass
    return False


def _is_server_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return bool(isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout)))


retry_on_rate_limit = retry(
    retry=retry_if_exception(_is_rate_limit),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    stop=stop_after_attempt(3),
    reraise=True,
)

retry_on_server_error = retry(
    retry=retry_if_exception(_is_server_error),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
