"""Tests for rate limit key extraction."""

from unittest.mock import MagicMock, patch

from app.rate_limit import _get_rate_limit_key


def _make_request(headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = headers or {}
    req.client.host = "127.0.0.1"
    return req


def test_rate_limit_key_uses_candidate_id_from_jwt():
    """Authenticated requests should use candidate_id as rate limit key."""
    req = _make_request({"authorization": "Bearer valid-token"})
    with patch("app.rate_limit.decode_token", return_value={"sub": "user-123"}):
        key = _get_rate_limit_key(req)
    assert key == "user:user-123"


def test_rate_limit_key_falls_back_on_jwt_decode_failure():
    """Invalid JWT should fall back to IP-based key."""
    req = _make_request({"authorization": "Bearer bad-token"})
    with (
        patch("app.rate_limit.decode_token", side_effect=Exception("Invalid")),
        patch("app.rate_limit.get_remote_address", return_value="10.0.0.1"),
    ):
        key = _get_rate_limit_key(req)
    assert key == "10.0.0.1"


def test_rate_limit_key_uses_cloudflare_ip():
    """Requests with CF-Connecting-IP header should use that IP."""
    req = _make_request({"cf-connecting-ip": "203.0.113.5"})
    key = _get_rate_limit_key(req)
    assert key == "203.0.113.5"


def test_rate_limit_key_no_auth_no_cf():
    """Unauthenticated requests without CF header use remote address."""
    req = _make_request({})
    with patch("app.rate_limit.get_remote_address", return_value="192.168.1.1"):
        key = _get_rate_limit_key(req)
    assert key == "192.168.1.1"
