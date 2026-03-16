"""Tests for the DNS health check service."""

from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

import app.services.dns_health_service as dns_mod
from app.services.dns_health_service import _resolve_txt, check_email_dns_health

DOMAIN = "example.com"

SPF_PASS = "v=spf1 include:amazonses.com ~all"
DKIM_PASS = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3..."
DMARC_PASS = "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"


def _make_resolve_txt(mapping: dict):
    """Return an async side_effect function that returns values by qname."""

    async def _resolve_txt(qname: str):
        return mapping.get(qname)

    return _resolve_txt


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the module-level cache before each test."""
    dns_mod._cache["result"] = None
    dns_mod._cache["expires_at"] = 0
    yield


@pytest.mark.asyncio
async def test_dns_health_all_pass():
    mapping = {
        DOMAIN: SPF_PASS,
        f"resend._domainkey.{DOMAIN}": DKIM_PASS,
        f"_dmarc.{DOMAIN}": DMARC_PASS,
    }
    with patch(
        "app.services.dns_health_service._resolve_txt",
        side_effect=_make_resolve_txt(mapping),
    ):
        result = await check_email_dns_health(DOMAIN, force=True)

    assert result["overall"] == "pass"
    assert result["spf"]["status"] == "pass"
    assert result["dkim"]["status"] == "pass"
    assert result["dmarc"]["status"] == "pass"
    assert result["domain"] == DOMAIN


@pytest.mark.asyncio
async def test_dns_health_spf_missing_is_fail():
    # No SPF record at all
    mapping = {
        f"resend._domainkey.{DOMAIN}": DKIM_PASS,
        f"_dmarc.{DOMAIN}": DMARC_PASS,
    }
    with patch(
        "app.services.dns_health_service._resolve_txt",
        side_effect=_make_resolve_txt(mapping),
    ):
        result = await check_email_dns_health(DOMAIN, force=True)

    assert result["overall"] == "fail"
    assert result["spf"]["status"] == "fail"


@pytest.mark.asyncio
async def test_dns_health_dmarc_missing_is_warning():
    # SPF present, DKIM present, DMARC missing
    mapping = {
        DOMAIN: SPF_PASS,
        f"resend._domainkey.{DOMAIN}": DKIM_PASS,
        # _dmarc.example.com returns None (not in mapping)
    }
    with patch(
        "app.services.dns_health_service._resolve_txt",
        side_effect=_make_resolve_txt(mapping),
    ):
        result = await check_email_dns_health(DOMAIN, force=True)

    assert result["overall"] == "warning"
    assert result["spf"]["status"] == "pass"
    assert result["dkim"]["status"] == "pass"
    assert result["dmarc"]["status"] == "fail"
    assert result["dmarc"]["recommendation"] is not None


@pytest.mark.asyncio
async def test_dns_health_uses_configurable_dkim_selector():
    """The DKIM lookup qname must use the configured DKIM_SELECTOR."""
    custom_selector = "mail"
    captured_qnames: list[str] = []

    async def _capture_resolve_txt(qname: str):
        captured_qnames.append(qname)
        if qname == DOMAIN:
            return SPF_PASS
        if f"{custom_selector}._domainkey." in qname:
            return DKIM_PASS
        if "_dmarc." in qname:
            return DMARC_PASS
        return None

    with patch("app.services.dns_health_service.settings") as mock_settings:
        mock_settings.DKIM_SELECTOR = custom_selector
        mock_settings.SPF_EXPECTED_INCLUDES = ["amazonses.com", "resend.com"]
        mock_settings.DNS_HEALTH_CACHE_TTL = 300
        with patch(
            "app.services.dns_health_service._resolve_txt",
            side_effect=_capture_resolve_txt,
        ):
            result = await check_email_dns_health(DOMAIN, force=True)

    dkim_qname = f"{custom_selector}._domainkey.{DOMAIN}"
    assert dkim_qname in captured_qnames, f"Expected DKIM qname '{dkim_qname}' in lookups, got: {captured_qnames}"
    assert result["dkim"]["selector"] == custom_selector


@pytest.mark.asyncio
async def test_admin_email_health_endpoint(client):
    """GET /api/v1/admin/email-health returns overall/spf/dkim/dmarc keys."""
    import uuid

    from app.utils.security import hash_password

    # We need a db session - use the client fixture's underlying session via the app's
    # dependency override. Instead, create an admin user via the registration + direct
    # DB approach used elsewhere. Here we use the client fixture (which has db_session
    # injected) by monkey-patching the dependency in the test itself.

    mapping = {
        DOMAIN: SPF_PASS,
        f"resend._domainkey.{DOMAIN}": DKIM_PASS,
        f"_dmarc.{DOMAIN}": DMARC_PASS,
    }

    from app.dependencies import get_current_admin
    from app.main import app as _app
    from app.models.candidate import Candidate as _Candidate

    # Create a fake admin candidate for DI override
    fake_admin = _Candidate(
        id=uuid.uuid4(),
        email="admin-health-test@example.com",
        full_name="Health Admin",
        is_admin=True,
        password_hash=hash_password("x"),
    )

    async def _override_admin():
        return fake_admin

    _app.dependency_overrides[get_current_admin] = _override_admin

    try:
        with (
            patch(
                "app.services.dns_health_service._resolve_txt",
                side_effect=_make_resolve_txt(mapping),
            ),
            patch("app.api.admin.settings") as mock_settings,
        ):
            mock_settings.SENDER_EMAIL = f"noreply@{DOMAIN}"
            resp = await client.get("/api/v1/admin/email-health?force=true")

        assert resp.status_code == 200
        body = resp.json()
        assert "overall" in body
        assert "spf" in body
        assert "dkim" in body
        assert "dmarc" in body
    finally:
        _app.dependency_overrides.pop(get_current_admin, None)


# ---------------------------------------------------------------------------
# _resolve_txt direct tests (covers lines 18-45)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_txt_success():
    """Successful TXT resolution returns concatenated text."""
    mock_rdata = MagicMock()
    mock_rdata.strings = [b"v=spf1 include:example.com ~all"]
    mock_answer = [mock_rdata]

    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(return_value=mock_answer)

    with patch("app.services.dns_health_service.dns.asyncresolver.Resolver", return_value=mock_resolver):
        result = await _resolve_txt("example.com")

    assert result == "v=spf1 include:example.com ~all"


@pytest.mark.asyncio
async def test_resolve_txt_nxdomain_returns_none():
    """NXDOMAIN should return None (domain not found)."""
    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

    with patch("app.services.dns_health_service.dns.asyncresolver.Resolver", return_value=mock_resolver):
        result = await _resolve_txt("nonexistent.example.com")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_txt_timeout_raises():
    """DNS timeout should raise TimeoutError."""
    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.LifetimeTimeout(timeout=5.0, errors={}))

    with (
        patch("app.services.dns_health_service.dns.asyncresolver.Resolver", return_value=mock_resolver),
        pytest.raises(TimeoutError, match="DNS lookup timed out"),
    ):
        await _resolve_txt("slow.example.com")


@pytest.mark.asyncio
async def test_resolve_txt_generic_error_returns_none():
    """Unexpected errors should return None (graceful degradation)."""
    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(side_effect=RuntimeError("unexpected"))

    with patch("app.services.dns_health_service.dns.asyncresolver.Resolver", return_value=mock_resolver):
        result = await _resolve_txt("broken.example.com")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_txt_no_answer_returns_none():
    """NoAnswer should return None."""
    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NoAnswer())

    with patch("app.services.dns_health_service.dns.asyncresolver.Resolver", return_value=mock_resolver):
        result = await _resolve_txt("no-txt.example.com")

    assert result is None
