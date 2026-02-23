"""End-to-end flow test: register → resume → discover → outreach → analytics."""
import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_full_e2e_flow(client: AsyncClient, invite_code: str):
    # 1. Register
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "e2e@example.com", "password": "securepass1", "full_name": "E2E Tester", "invite_code": invite_code},
    )
    assert resp.status_code == 201

    # 2. Login
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "e2e@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 200
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 3. Set target preferences
    resp = await client.patch(
        f"{API}/auth/me",
        headers=headers,
        json={
            "target_roles": ["Staff Engineer"],
            "target_industries": ["fintech", "saas"],
            "target_locations": ["Remote", "Tel Aviv"],
            "salary_min": 150000,
            "salary_max": 250000,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["target_roles"] == ["Staff Engineer"]

    # 4. Discover companies
    resp = await client.post(f"{API}/companies/discover", headers=headers)
    assert resp.status_code == 200
    discovered = resp.json()
    assert discovered["total"] > 0

    # 5. Get suggested companies
    resp = await client.get(f"{API}/companies/suggested", headers=headers)
    assert resp.status_code == 200
    suggested = resp.json()
    assert suggested["total"] > 0

    # 6. Approve top company
    company_id = suggested["companies"][0]["id"]
    resp = await client.post(f"{API}/companies/{company_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # 7. Manually add a company
    resp = await client.post(
        f"{API}/companies/add",
        headers=headers,
        json={"domain": "datadog.com"},
    )
    assert resp.status_code == 201
    manual_company_id = resp.json()["id"]

    # 8. Get contacts at manual company
    resp = await client.get(
        f"{API}/companies/{manual_company_id}/contacts",
        headers=headers,
    )
    assert resp.status_code == 200
    contacts = resp.json()
    assert len(contacts) > 0

    contact_id = contacts[0]["id"]

    # 9. Verify contact
    resp = await client.post(
        f"{API}/contacts/{contact_id}/verify",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["email_verified"] is True

    # 10. Draft outreach
    resp = await client.post(
        f"{API}/outreach/draft",
        headers=headers,
        json={"contact_id": contact_id},
    )
    assert resp.status_code == 201
    draft = resp.json()
    assert draft["status"] == "draft"
    assert draft["body"]
    message_id = draft["id"]

    # 11. Edit draft
    resp = await client.patch(
        f"{API}/outreach/{message_id}",
        headers=headers,
        json={"body": "Customized outreach message for E2E test."},
    )
    assert resp.status_code == 200

    # 12. Send
    resp = await client.post(f"{API}/outreach/{message_id}/send", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"

    # 13. Simulate webhook (open event)
    resp = await client.post(
        f"{API}/webhooks/resend",
        json={
            "type": "email.opened",
            "data": {"email_id": resp.json().get("id", "mock_id")},
        },
    )
    assert resp.status_code == 200

    # 14. Check funnel
    resp = await client.get(f"{API}/analytics/funnel", headers=headers)
    assert resp.status_code == 200
    funnel = resp.json()
    assert funnel["sent"] >= 1

    # 15. Check pipeline
    resp = await client.get(f"{API}/analytics/pipeline", headers=headers)
    assert resp.status_code == 200
    pipeline = resp.json()
    assert pipeline["approved"] >= 1

    # 16. Check outreach stats
    resp = await client.get(f"{API}/analytics/outreach", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_sent"] >= 1

    # 17. List all outreach
    resp = await client.get(f"{API}/outreach", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
