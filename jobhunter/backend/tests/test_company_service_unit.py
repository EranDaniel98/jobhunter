"""Unit tests for company_service - no real DB/Redis/OpenAI required."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestGetCompanySizeTier:
    def test_none_returns_medium(self):
        from app.services.company_service import get_company_size_tier

        assert get_company_size_tier(None) == "medium"

    def test_small_company(self):
        from app.services.company_service import get_company_size_tier

        assert get_company_size_tier("11-50") == "small"

    def test_medium_company(self):
        from app.services.company_service import get_company_size_tier

        assert get_company_size_tier("51-200") == "medium"

    def test_large_company(self):
        from app.services.company_service import get_company_size_tier

        assert get_company_size_tier("1000+") == "large"

    def test_invalid_string_returns_medium(self):
        from app.services.company_service import get_company_size_tier

        assert get_company_size_tier("bogus") == "medium"


class TestComputeContactPriority:
    def test_vp_role_is_hiring_manager_and_decision_maker(self):
        from app.services.company_service import compute_contact_priority

        role_type, is_dm, priority = compute_contact_priority("VP Engineering", "small")
        assert role_type == "hiring_manager"
        assert is_dm is True
        assert priority > 0

    def test_manager_role_type_is_team_lead(self):
        from app.services.company_service import compute_contact_priority

        role_type, _is_dm, _priority = compute_contact_priority("Engineering Manager", "medium")
        assert role_type == "team_lead"

    def test_recruiter_role_type(self):
        from app.services.company_service import compute_contact_priority

        role_type, _is_dm, _priority = compute_contact_priority("Technical Recruiter", "large")
        assert role_type == "recruiter"

    def test_unknown_role_returns_other(self):
        from app.services.company_service import compute_contact_priority

        role_type, _is_dm, priority = compute_contact_priority("Intern", "small")
        assert role_type == "other"
        assert priority == 0


class TestValidateDiscoveryResult:
    def test_valid_when_no_filters(self):
        from app.services.company_service import _validate_discovery_result

        ok, _reason = _validate_discovery_result(
            {"name": "Acme", "domain": "acme.com", "size": "51-200", "location": "New York"},
            {},
        )
        assert ok is True

    def test_size_filter_mismatch_fails(self):
        from app.services.company_service import _validate_discovery_result

        ok, _reason = _validate_discovery_result(
            {"name": "BigCorp", "domain": "bigcorp.com", "size": "5000+", "location": "Remote"},
            {"company_size": "1-50", "locations": [], "includes_remote": False},
        )
        assert ok is False

    def test_location_filter_mismatch_fails(self):
        from app.services.company_service import _validate_discovery_result

        ok, _reason = _validate_discovery_result(
            {"name": "EuropeCo", "domain": "europeco.com", "size": "51-200", "location": "Berlin, Germany"},
            {"company_size": None, "locations": ["New York"], "includes_remote": False},
        )
        assert ok is False

    def test_location_filter_passes_with_includes_remote(self):
        from app.services.company_service import _validate_discovery_result

        ok, _reason = _validate_discovery_result(
            {"name": "RemoteCo", "domain": "remoteco.com", "size": "51-200", "location": "Worldwide"},
            {"company_size": None, "locations": ["New York"], "includes_remote": True},
        )
        assert ok is True


# ---------------------------------------------------------------------------
# discover_companies
# ---------------------------------------------------------------------------


def _make_candidate(candidate_id=None):
    c = MagicMock()
    c.id = candidate_id or uuid.uuid4()
    c.target_industries = ["technology"]
    c.target_roles = ["software engineer"]
    c.target_locations = ["Remote"]
    c.email = "test@example.com"
    return c


def _make_dna(candidate_id=None):
    d = MagicMock()
    d.candidate_id = candidate_id or uuid.uuid4()
    d.experience_summary = "Senior engineer with Python and cloud experience"
    d.embedding = [0.1] * 128
    return d


class TestDiscoverCompanies:
    @pytest.mark.asyncio
    async def test_raises_when_candidate_not_found(self):
        from app.services.company_service import discover_companies

        mock_db = AsyncMock()
        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = cand_result

        with pytest.raises(ValueError, match="Candidate not found"):
            await discover_companies(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_dna(self):
        from app.services.company_service import discover_companies

        candidate = _make_candidate()
        mock_db = AsyncMock()

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = candidate

        dna_result = MagicMock()
        dna_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [cand_result, dna_result]

        with patch("app.services.company_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.HUNTER_API_KEY = "test-key"
            with pytest.raises(ValueError, match="Upload and process a resume"):
                await discover_companies(mock_db, candidate.id)

    @pytest.mark.asyncio
    async def test_raises_when_no_openai_key(self):
        from app.services.company_service import discover_companies

        candidate = _make_candidate()
        dna = _make_dna(candidate.id)
        mock_db = AsyncMock()

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = candidate

        dna_result = MagicMock()
        dna_result.scalar_one_or_none.return_value = dna

        mock_db.execute.side_effect = [cand_result, dna_result]

        with patch("app.services.company_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.HUNTER_API_KEY = "test-key"
            with pytest.raises(ValueError, match="OpenAI"):
                await discover_companies(mock_db, candidate.id)

    @pytest.mark.asyncio
    async def test_discovers_companies_success(self):
        from app.services.company_service import discover_companies

        candidate = _make_candidate()
        dna = _make_dna(candidate.id)
        mock_db = AsyncMock()

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = candidate

        dna_result = MagicMock()
        dna_result.scalar_one_or_none.return_value = dna

        # existing domains query
        existing_result = MagicMock()
        existing_result.all.return_value = []  # no existing companies

        mock_db.execute.side_effect = [cand_result, dna_result, existing_result]

        openai_client = AsyncMock()
        openai_client.parse_structured.return_value = {
            "companies": [
                {
                    "domain": "newco.com",
                    "name": "NewCo",
                    "reason": "Good match",
                    "industry": "technology",
                    "size": "51-200",
                    "location": "Remote",
                    "tech_stack": ["Python"],
                }
            ]
        }

        hunter_client = AsyncMock()
        hunter_client.domain_search.return_value = {
            "organization": "NewCo",
            "description": "A tech company",
            "industry": "technology",
            "size": "51-200",
            "location": "Remote",
            "technologies": ["Python"],
            "emails": [],
        }

        # _create_company_from_hunter calls embed_text if dna.embedding is not None
        with (
            patch("app.services.company_service.settings") as mock_settings,
            patch("app.services.company_service.get_openai", return_value=openai_client),
            patch("app.services.company_service.get_hunter", return_value=hunter_client),
            patch(
                "app.services.company_service.embed_text",
                new_callable=AsyncMock,
                return_value=[0.1] * 128,
            ),
        ):
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.HUNTER_API_KEY = "test-key"
            companies = await discover_companies(mock_db, candidate.id)

        assert len(companies) == 1
        assert companies[0].domain == "newco.com"


# ---------------------------------------------------------------------------
# recalculate_fit_scores
# ---------------------------------------------------------------------------


class TestRecalculateFitScores:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_dna(self):
        from app.services.company_service import recalculate_fit_scores

        mock_db = AsyncMock()
        dna_result = MagicMock()
        dna_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = dna_result

        count = await recalculate_fit_scores(mock_db, uuid.uuid4())
        assert count == 0

    @pytest.mark.asyncio
    async def test_recalculates_scores_for_companies(self):
        from app.services.company_service import recalculate_fit_scores

        candidate_id = uuid.uuid4()
        dna = _make_dna(candidate_id)

        company = MagicMock()
        company.embedding = [0.2] * 128
        company.fit_score = 0.5

        mock_db = AsyncMock()

        dna_result = MagicMock()
        dna_result.scalar_one_or_none.return_value = dna

        companies_result = MagicMock()
        companies_result.scalars.return_value.all.return_value = [company]

        mock_db.execute.side_effect = [dna_result, companies_result]

        with patch("app.services.company_service.cosine_similarity", return_value=0.9):
            count = await recalculate_fit_scores(mock_db, candidate_id)

        # fit_score was 0.5, now 0.9 → updated
        assert count == 1
        assert company.fit_score == 0.9
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# approve_company / reject_company
# ---------------------------------------------------------------------------


class TestApproveCompany:
    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        from app.services.company_service import approve_company

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Company not found"):
            await approve_company(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_rejected(self):
        from app.models.enums import CompanyStatus
        from app.services.company_service import approve_company

        company = MagicMock()
        company.status = CompanyStatus.REJECTED
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = company
        mock_db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Cannot approve"):
            await approve_company(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_sets_status_approved(self):
        from app.models.enums import CompanyStatus
        from app.services.company_service import approve_company

        company = MagicMock()
        company.status = CompanyStatus.SUGGESTED
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = company
        mock_db.execute.return_value = result_mock

        returned = await approve_company(mock_db, company.id)
        assert company.status == "approved"
        assert returned is company


class TestRejectCompany:
    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        from app.services.company_service import reject_company

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="Company not found"):
            await reject_company(mock_db, uuid.uuid4(), "Not interested")

    @pytest.mark.asyncio
    async def test_sets_status_rejected_and_stores_reason(self):
        from app.services.company_service import reject_company

        company = MagicMock()
        company.status = "suggested"
        company.hunter_data = {}
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = company
        mock_db.execute.return_value = result_mock

        returned = await reject_company(mock_db, company.id, "Not a fit")
        assert company.status == "rejected"
        assert returned is company
