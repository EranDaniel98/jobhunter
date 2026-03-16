"""Extended unit tests for the apply API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import JobPostingStatus
from app.models.job_posting import JobPosting

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


async def _make_posting(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    title: str = "Test Job",
    status: JobPostingStatus = JobPostingStatus.PENDING,
) -> JobPosting:
    posting = JobPosting(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        title=title,
        company_name="TestCorp",
        raw_text="Some job description text.",
        status=status,
    )
    db.add(posting)
    await db.flush()
    return posting


# ---------------------------------------------------------------------------
# POST /apply/analyze
# ---------------------------------------------------------------------------


class TestApplyAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_creates_posting(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/apply/analyze",
            headers=auth_headers,
            json={
                "title": "Backend Engineer",
                "company_name": "AnalyzeCo",
                "raw_text": "We need a backend engineer with Python expertise.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Backend Engineer"
        assert data["status"] == "pending"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_analyze_requires_raw_text(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/apply/analyze",
            headers=auth_headers,
            json={"title": "No Text Job"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_with_optional_fields(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            f"{API}/apply/analyze",
            headers=auth_headers,
            json={
                "title": "Full Stack Dev",
                "raw_text": "Looking for a full stack developer.",
                "url": "https://example.com/jobs/123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Full Stack Dev"

    @pytest.mark.asyncio
    async def test_analyze_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            f"{API}/apply/analyze",
            json={"title": "Job", "raw_text": "Text"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_analyze_appears_in_list(self, client: AsyncClient, auth_headers: dict):
        title = f"UniqueJob-{uuid.uuid4().hex[:8]}"
        await client.post(
            f"{API}/apply/analyze",
            headers=auth_headers,
            json={"title": title, "raw_text": "Job text here."},
        )
        list_resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
        titles = [p["title"] for p in list_resp.json()["postings"]]
        assert title in titles


# ---------------------------------------------------------------------------
# GET /apply/postings
# ---------------------------------------------------------------------------


class TestApplyListPostings:
    @pytest.mark.asyncio
    async def test_list_postings_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "postings" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_postings_after_analyze(self, client: AsyncClient, auth_headers: dict):
        await client.post(
            f"{API}/apply/analyze",
            headers=auth_headers,
            json={"title": "List Test Job", "raw_text": "Description."},
        )
        resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_postings_pagination(self, client: AsyncClient, auth_headers: dict):
        # Create a couple of postings
        for i in range(3):
            await client.post(
                f"{API}/apply/analyze",
                headers=auth_headers,
                json={"title": f"Paginated Job {i}", "raw_text": "Description."},
            )
        resp = await client.get(
            f"{API}/apply/postings",
            headers=auth_headers,
            params={"skip": 0, "limit": 2},
        )
        data = resp.json()
        assert len(data["postings"]) <= 2

    @pytest.mark.asyncio
    async def test_list_postings_requires_auth(self, client: AsyncClient):
        resp = await client.get(f"{API}/apply/postings")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_postings_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        invite_code: str,
    ):
        """Postings from another user should NOT appear in this user's list."""
        # Create another user
        other_email = f"other-{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            f"{API}/auth/register",
            json={
                "email": other_email,
                "password": "testpass123",
                "full_name": "Other User",
                "invite_code": invite_code,
            },
        )
        other_resp = await client.post(
            f"{API}/auth/login",
            json={"email": other_email, "password": "testpass123"},
        )
        other_headers = {"Authorization": f"Bearer {other_resp.json()['access_token']}"}

        # Other user creates a posting
        other_title = f"OtherJob-{uuid.uuid4().hex[:8]}"
        await client.post(
            f"{API}/apply/analyze",
            headers=other_headers,
            json={"title": other_title, "raw_text": "Other description."},
        )

        # Current user should not see it
        resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
        titles = [p["title"] for p in resp.json()["postings"]]
        assert other_title not in titles


# ---------------------------------------------------------------------------
# GET /apply/postings/{id}/analysis — already-pending posting
# ---------------------------------------------------------------------------


class TestApplyGetAnalysis:
    @pytest.mark.asyncio
    async def test_analysis_pending_returns_202(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        # Get the candidate id
        me = await client.get(f"{API}/auth/me", headers=auth_headers)
        candidate_id = uuid.UUID(me.json()["id"])

        posting = await _make_posting(db_session, candidate_id, status=JobPostingStatus.PENDING)

        resp = await client.get(
            f"{API}/apply/postings/{posting.id}/analysis",
            headers=auth_headers,
        )
        # Pending → 202
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_analysis_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            f"{API}/apply/postings/{uuid.uuid4()}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /apply/postings/{id}/stage
# ---------------------------------------------------------------------------


class TestApplyUpdateStage:
    @pytest.mark.asyncio
    async def test_update_stage(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        me = await client.get(f"{API}/auth/me", headers=auth_headers)
        candidate_id = uuid.UUID(me.json()["id"])
        posting = await _make_posting(db_session, candidate_id)

        resp = await client.patch(
            f"{API}/apply/postings/{posting.id}/stage",
            headers=auth_headers,
            json={"stage": "applied"},
        )
        assert resp.status_code == 200
        assert resp.json()["application_stage"] == "applied"

    @pytest.mark.asyncio
    async def test_update_stage_invalid_value(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        me = await client.get(f"{API}/auth/me", headers=auth_headers)
        candidate_id = uuid.UUID(me.json()["id"])
        posting = await _make_posting(db_session, candidate_id)

        resp = await client.patch(
            f"{API}/apply/postings/{posting.id}/stage",
            headers=auth_headers,
            json={"stage": "totally_invalid"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_stage_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.patch(
            f"{API}/apply/postings/{uuid.uuid4()}/stage",
            headers=auth_headers,
            json={"stage": "applied"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /apply/postings/{id}
# ---------------------------------------------------------------------------


class TestApplyDeletePosting:
    @pytest.mark.asyncio
    async def test_delete_posting(self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
        me = await client.get(f"{API}/auth/me", headers=auth_headers)
        candidate_id = uuid.UUID(me.json()["id"])
        posting = await _make_posting(db_session, candidate_id)

        resp = await client.delete(f"{API}/apply/postings/{posting.id}", headers=auth_headers)
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_posting_not_found(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete(f"{API}/apply/postings/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404
