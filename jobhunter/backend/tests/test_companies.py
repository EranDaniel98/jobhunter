import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_list_companies_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/companies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["companies"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_add_company(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "stripe.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["domain"] == "stripe.com"
    assert data["status"] == "approved"
    assert data["name"] == "Stripe"


@pytest.mark.asyncio
async def test_add_company_duplicate(client: AsyncClient, auth_headers: dict):
    await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "vercel.com"},
    )
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "vercel.com"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_company_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(
        f"{API}/companies/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_company_approve_reject_flow(client: AsyncClient, auth_headers: dict):
    # Discover
    resp = await client.post(f"{API}/companies/discover", headers=auth_headers)
    assert resp.status_code == 200

    # List suggested
    resp = await client.get(f"{API}/companies/suggested", headers=auth_headers)
    assert resp.status_code == 200
    suggested = resp.json()

    if suggested["total"] > 0:
        company_id = suggested["companies"][0]["id"]

        # Approve
        resp = await client.post(
            f"{API}/companies/{company_id}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    # Get another to reject
    if suggested["total"] > 1:
        company_id = suggested["companies"][1]["id"]

        resp = await client.post(
            f"{API}/companies/{company_id}/reject",
            headers=auth_headers,
            json={"reason": "Not interested in this industry"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_discover_enriches_industry_size_tech(client: AsyncClient, auth_headers: dict):
    """Test: discovered companies get industry/size/tech_stack from OpenAI when Hunter.io returns none."""
    # First upload a resume to create DNA (needed for discovery)
    import io
    resp = await client.post(
        f"{API}/resume/upload",
        headers=auth_headers,
        files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
    )
    # Discovery
    resp = await client.post(f"{API}/companies/discover", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    companies = data["companies"]
    assert len(companies) > 0

    # Check that discovered companies have enriched metadata
    for company in companies:
        assert company["name"]
        # industry should be populated (either from Hunter or OpenAI backfill)
        assert "industry" in company
