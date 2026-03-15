import time
from datetime import UTC

import dns.asyncresolver
import dns.exception
import dns.resolver
import structlog

from app.config import settings

logger = structlog.get_logger()

_cache: dict = {"result": None, "expires_at": 0}


async def _resolve_txt(qname: str) -> str | None:
    """Resolve a TXT record, returning the concatenated text or None."""
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = settings.DNS_LOOKUP_TIMEOUT
        answers = await resolver.resolve(qname, "TXT")
        texts = []
        for rdata in answers:
            texts.append(b"".join(rdata.strings).decode())
        return " ".join(texts)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return None
    except (dns.resolver.LifetimeTimeout, dns.exception.Timeout):
        logger.warning(
            "dns_health.lookup_timeout",
            extra={
                "feature": "dns_health",
                "detail": {"qname": qname},
            },
        )
        raise TimeoutError(f"DNS lookup timed out for {qname}") from None
    except Exception:
        logger.error(
            "dns_health.lookup_error",
            extra={
                "feature": "dns_health",
                "detail": {"qname": qname},
            },
        )
        return None


async def check_email_dns_health(domain: str, force: bool = False) -> dict:
    """Check SPF, DKIM, and DMARC records for a domain."""
    now = time.time()
    if not force and _cache["result"] and _cache["expires_at"] > now:
        return _cache["result"]

    spf_record = None
    spf_status = "fail"
    dkim_status = "fail"
    dmarc_status = "fail"
    dmarc_record = None
    dmarc_recommendation = None

    # SPF
    try:
        txt = await _resolve_txt(domain)
        if txt and "v=spf1" in txt:
            spf_record = txt
            if any(inc in txt for inc in settings.SPF_EXPECTED_INCLUDES):
                spf_status = "pass"
    except TimeoutError:
        spf_status = "timeout"

    # DKIM
    try:
        dkim_qname = f"{settings.DKIM_SELECTOR}._domainkey.{domain}"
        txt = await _resolve_txt(dkim_qname)
        if txt and ("v=DKIM1" in txt or "k=rsa" in txt):
            dkim_status = "pass"
    except TimeoutError:
        dkim_status = "timeout"

    # DMARC
    try:
        dmarc_qname = f"_dmarc.{domain}"
        txt = await _resolve_txt(dmarc_qname)
        if txt and "v=DMARC1" in txt:
            dmarc_status = "pass"
            dmarc_record = txt
        else:
            dmarc_recommendation = "Add a DMARC record: v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"
    except TimeoutError:
        dmarc_status = "timeout"

    # Overall
    if spf_status == "fail":
        overall = "fail"
    elif all(s == "pass" for s in [spf_status, dkim_status, dmarc_status]):
        overall = "pass"
    else:
        overall = "warning"

    from datetime import datetime

    result = {
        "domain": domain,
        "spf": {"status": spf_status, "record": spf_record},
        "dkim": {"status": dkim_status, "selector": settings.DKIM_SELECTOR},
        "dmarc": {
            "status": dmarc_status,
            "record": dmarc_record,
            "recommendation": dmarc_recommendation,
        },
        "overall": overall,
        "checked_at": datetime.now(UTC).isoformat(),
    }

    _cache["result"] = result
    _cache["expires_at"] = now + settings.DNS_HEALTH_CACHE_TTL

    logger.info(
        "dns_health.check_complete",
        extra={
            "feature": "dns_health",
            "detail": {"spf": spf_status, "dkim": dkim_status, "dmarc": dmarc_status, "overall": overall},
        },
    )

    return result
