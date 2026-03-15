"""Tests for the DNS health check service."""
import pytest
from unittest.mock import AsyncMock, patch

import app.services.dns_health_service as dns_mod
from app.services.dns_health_service import check_email_dns_health


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
    assert dkim_qname in captured_qnames, (
        f"Expected DKIM qname '{dkim_qname}' in lookups, got: {captured_qnames}"
    )
    assert result["dkim"]["selector"] == custom_selector
