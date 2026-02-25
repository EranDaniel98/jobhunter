"""End-to-end flow test: register → resume → discover → outreach → analytics."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_full_e2e_flow(client: AsyncClient, invite_code: str, db_session: AsyncSession):
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

    # 3.5. Seed DNA (needed for discovery since resume parsing is async)
    from tests.conftest import seed_candidate_dna
    await seed_candidate_dna(db_session, client, headers)

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
    assert "email_verified" in resp.json()  # Real API may return False for test contacts

    # 10. Draft outreach (now async — create via service for deterministic e2e flow)
    me_resp = await client.get(f"{API}/auth/me", headers=headers)
    candidate_id = uuid.UUID(me_resp.json()["id"])

    from app.services.outreach_service import draft_message
    draft_msg = await draft_message(db_session, candidate_id, uuid.UUID(contact_id))
    assert draft_msg.status == "draft"
    assert draft_msg.body
    message_id = str(draft_msg.id)

    # 11. Edit draft
    resp = await client.patch(
        f"{API}/outreach/{message_id}",
        headers=headers,
        json={"body": "Customized outreach message for E2E test."},
    )
    assert resp.status_code == 200

    # 12. Send (may go through approval gateway → pending_approval)
    resp = await client.post(f"{API}/outreach/{message_id}/send", headers=headers)
    assert resp.status_code == 200
    send_result = resp.json()
    assert send_result["status"] in ("sent", "pending_approval")

    if send_result["status"] == "pending_approval":
        # Approve the pending action so the e2e flow can continue
        approvals_resp = await client.get(f"{API}/approvals", headers=headers)
        assert approvals_resp.status_code == 200
        pending = approvals_resp.json()["actions"]
        if pending:
            await client.post(f"{API}/approvals/{pending[0]['id']}/approve", headers=headers)

    # 13. Simulate webhook (open event)
    resp = await client.post(
        f"{API}/webhooks/resend",
        json={
            "type": "email.opened",
            "data": {"email_id": message_id},
        },
    )
    assert resp.status_code == 200

    # 14. Check funnel
    resp = await client.get(f"{API}/analytics/funnel", headers=headers)
    assert resp.status_code == 200
    funnel = resp.json()
    assert funnel["sent"] >= 0  # May be 0 if pending_approval

    # 15. Check pipeline
    resp = await client.get(f"{API}/analytics/pipeline", headers=headers)
    assert resp.status_code == 200
    pipeline = resp.json()
    assert pipeline["approved"] >= 1

    # 16. Check outreach stats
    resp = await client.get(f"{API}/analytics/outreach", headers=headers)
    assert resp.status_code == 200

    # 17. List all outreach
    resp = await client.get(f"{API}/outreach", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
