import pytest


@pytest.fixture
async def auth_headers_for_incidents(client, invite_code):
    """Register and login a user, return auth headers."""
    await client.post("/api/v1/auth/register", json={
        "email": "incident_user@test.com",
        "password": "TestPass123!",
        "full_name": "Incident User",
        "invite_code": invite_code,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "incident_user@test.com",
        "password": "TestPass123!",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_submit_incident_success(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "Button does not work",
            "description": "The submit button on the dashboard is unresponsive.",
            "context": '{"email":"incident_user@test.com","plan_tier":"free"}',
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "bug"
    assert body["title"] == "Button does not work"
    assert body["github_status"] == "synced"
    assert body["github_issue_url"] is not None


async def test_submit_incident_invalid_category(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "invalid",
            "title": "Test",
            "description": "Test",
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 400


async def test_submit_incident_title_too_long(client, auth_headers_for_incidents):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "x" * 201,
            "description": "Test",
        },
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 400


async def test_submit_incident_unauthenticated(client):
    resp = await client.post(
        "/api/v1/incidents",
        data={
            "category": "bug",
            "title": "Test",
            "description": "Test",
        },
    )
    assert resp.status_code == 403 or resp.status_code == 401


async def test_list_incidents_admin_only(client, auth_headers_for_incidents):
    resp = await client.get(
        "/api/v1/incidents",
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 403


async def test_incident_stats_admin_only(client, auth_headers_for_incidents):
    resp = await client.get(
        "/api/v1/incidents/stats",
        headers=auth_headers_for_incidents,
    )
    assert resp.status_code == 403
