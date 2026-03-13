"""Tests for app/utils/retry.py -- retry decorators."""

import httpx

from app.utils.retry import (
    _is_rate_limit,
    _is_server_error,
    retry_on_rate_limit,
    retry_on_server_error,
)

# ---------------------------------------------------------------------------
# _is_rate_limit
# ---------------------------------------------------------------------------


def _make_http_error(status_code: int) -> httpx.HTTPStatusError:
    response = httpx.Response(status_code=status_code, request=httpx.Request("GET", "http://x"))
    return httpx.HTTPStatusError("err", request=response.request, response=response)


def test_is_rate_limit_429():
    assert _is_rate_limit(_make_http_error(429)) is True


def test_is_rate_limit_500():
    assert _is_rate_limit(_make_http_error(500)) is False


def test_is_rate_limit_random_exception():
    assert _is_rate_limit(ValueError("nope")) is False


# ---------------------------------------------------------------------------
# _is_server_error
# ---------------------------------------------------------------------------


def test_is_server_error_500():
    assert _is_server_error(_make_http_error(500)) is True


def test_is_server_error_502():
    assert _is_server_error(_make_http_error(502)) is True


def test_is_server_error_429():
    assert _is_server_error(_make_http_error(429)) is False


def test_is_server_error_connect_error():
    assert _is_server_error(httpx.ConnectError("fail")) is True


def test_is_server_error_read_timeout():
    assert _is_server_error(httpx.ReadTimeout("timeout")) is True


def test_is_server_error_random_exception():
    assert _is_server_error(ValueError("nope")) is False


# ---------------------------------------------------------------------------
# Decorated functions work
# ---------------------------------------------------------------------------


def test_retry_on_rate_limit_succeeds_immediately():
    call_count = 0

    @retry_on_rate_limit
    def do_work():
        nonlocal call_count
        call_count += 1
        return "ok"

    assert do_work() == "ok"
    assert call_count == 1


def test_retry_on_server_error_succeeds_immediately():
    call_count = 0

    @retry_on_server_error
    def do_work():
        nonlocal call_count
        call_count += 1
        return "ok"

    assert do_work() == "ok"
    assert call_count == 1
