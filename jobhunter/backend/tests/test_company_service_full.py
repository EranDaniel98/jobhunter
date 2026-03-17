"""Full coverage tests for company_service - fills gaps left by test_company_service_unit.py.

Does NOT overlap with test_company_service_unit.py which already covers:
- get_company_size_tier, compute_contact_priority, _validate_discovery_result (pure helpers)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_all(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _all_rows(values):
    r = MagicMock()
    r.all.return_value = values
    return r


# ---------------------------------------------------------------------------
# discover_companies - error branches (lines 325, 344, 351, 362, 367, 369)
# ---------------------------------------------------------------------------


class TestDiscoverCompaniesEarlyExits:
    @pytest.mark.asyncio
    async def test_raises_when_candidate_not_found(self):
        from app.services.company_service import discover_companies

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        with pytest.raises(ValueError, match="Candidate not found"):
            await discover_companies(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_dna(self):
        from app.services.company_service import discover_companies

        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(None),  # no DNA
        ]

        with pytest.raises(ValueError, match="Upload and process a resume"):
            await discover_companies(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_no_openai_key(self):
        from app.services.company_service import discover_companies

        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = [0.1, 0.2]
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),  # existing domains
        ]

        with patch("app.services.company_service.settings") as ms:
            ms.OPENAI_API_KEY = None
            ms.HUNTER_API_KEY = "hunter-key"
            with pytest.raises(ValueError, match="OpenAI API key"):
                await discover_companies(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_no_hunter_key(self):
        from app.services.company_service import discover_companies

        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = [0.1, 0.2]
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),  # existing domains
        ]

        with patch("app.services.company_service.settings") as ms:
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = None
            with pytest.raises(ValueError, match="Hunter API key"):
                await discover_companies(mock_db, uuid.uuid4())


# ---------------------------------------------------------------------------
# discover_companies - location constraint building (lines 344-362)
# ---------------------------------------------------------------------------


class TestDiscoverCompaniesLocationConstraint:
    def _make_discover_mocks(self, locations):
        """Return (candidate, dna, mock_db) with given locations."""
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = locations

        dna = MagicMock()
        dna.embedding = [0.1, 0.2]
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),  # existing domains
        ]
        return candidate, dna, mock_db

    @pytest.mark.asyncio
    async def test_physical_and_remote_location_constraint(self):
        """Both physical location AND remote → hybrid constraint phrase."""
        _, _, mock_db = self._make_discover_mocks(["New York", "Remote"])

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4())

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "physical office" in prompt_arg or "remote-friendly" in prompt_arg

    @pytest.mark.asyncio
    async def test_remote_only_location_constraint(self):
        """Remote only → prefer remote-friendly companies constraint."""
        _, _, mock_db = self._make_discover_mocks(["Remote"])

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4())

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "remote" in prompt_arg.lower()

    @pytest.mark.asyncio
    async def test_no_location_constraint(self):
        """No locations → no location preference message."""
        _, _, mock_db = self._make_discover_mocks([])

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4())

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "No location preference" in prompt_arg

    @pytest.mark.asyncio
    async def test_physical_only_location_constraint(self):
        """Physical-only locations → office/headquarters constraint."""
        _, _, mock_db = self._make_discover_mocks(["San Francisco"])

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4())

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "San Francisco" in prompt_arg


# ---------------------------------------------------------------------------
# discover_companies - filter instructions (lines 367-369)
# ---------------------------------------------------------------------------


class TestDiscoverCompaniesFilterInstructions:
    @pytest.mark.asyncio
    async def test_company_size_filter_included_in_prompt(self):
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = [0.1, 0.2]
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),
        ]

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4(), company_size="51-200")

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "51-200" in prompt_arg

    @pytest.mark.asyncio
    async def test_keywords_filter_included_in_prompt(self):
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = [0.1, 0.2]
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),
        ]

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": []})
        mock_hunter = AsyncMock()

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            await discover_companies(mock_db, uuid.uuid4(), keywords="machine learning")

        prompt_arg = mock_openai.parse_structured.call_args[0][0]
        assert "machine learning" in prompt_arg


# ---------------------------------------------------------------------------
# discover_companies - validation retry + domain dedup (lines 401, 404, 413-433)
# ---------------------------------------------------------------------------


class TestDiscoverCompaniesValidationRetry:
    @pytest.mark.asyncio
    async def test_retry_triggered_when_too_few_valid_results(self):
        """When initial suggestions fail validation, a retry with corrected prompt is issued."""
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = None  # skip fit score
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),  # no existing domains
        ]

        # First call: returns companies that fail size filter
        # Second call (retry): returns valid company
        bad_companies = [
            {
                "domain": "bigcorp.com",
                "name": "BigCorp",
                "reason": "...",
                "industry": "tech",
                "size": "10001+",  # too large
                "location": "NY",
                "tech_stack": [],
            }
        ]
        good_companies = [
            {
                "domain": "smallco.com",
                "name": "SmallCo",
                "reason": "...",
                "industry": "tech",
                "size": "11-50",
                "location": "NY",
                "tech_stack": [],
            }
        ]

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(
            side_effect=[
                {"companies": bad_companies},
                {"companies": good_companies},
            ]
        )

        mock_hunter = AsyncMock()
        mock_hunter.domain_search = AsyncMock(
            return_value={"organization": "SmallCo", "description": "A small company", "emails": []}
        )

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
            patch("app.services.company_service.embed_text", new_callable=AsyncMock, return_value=[0.1, 0.2]),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            result = await discover_companies(mock_db, uuid.uuid4(), company_size="11-50")

        # Retry was called
        assert mock_openai.parse_structured.await_count == 2
        assert len(result) == 1
        assert result[0].domain == "smallco.com"

    @pytest.mark.asyncio
    async def test_domain_dedup_in_retry_merge(self):
        """Domains already in valid_companies are not added again from retry results."""
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = None
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),
        ]

        # Both calls return the same domain
        same_company = {
            "domain": "acme.com",
            "name": "Acme",
            "reason": "...",
            "industry": "tech",
            "size": "11-50",
            "location": "NY",
            "tech_stack": [],
        }
        bad_company = {
            "domain": "bigcorp.com",
            "name": "BigCorp",
            "reason": "...",
            "industry": "tech",
            "size": "10001+",
            "location": "NY",
            "tech_stack": [],
        }

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(
            side_effect=[
                # First call: 1 valid + 1 bad (triggers retry since < 3 valid and violations)
                {"companies": [same_company, bad_company]},
                # Retry: returns same domain again (should be deduped)
                {"companies": [same_company]},
            ]
        )

        mock_hunter = AsyncMock()
        mock_hunter.domain_search = AsyncMock(return_value={"organization": "Acme", "description": "...", "emails": []})

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
            patch("app.services.company_service.embed_text", new_callable=AsyncMock, return_value=[0.1, 0.2]),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            result = await discover_companies(mock_db, uuid.uuid4(), company_size="11-50")

        # Only one company despite duplicate in retry
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_hunter_failure_for_domain_is_logged_and_skipped(self):
        """If Hunter lookup fails for a domain, it is skipped rather than raising."""
        candidate = MagicMock()
        candidate.target_industries = ["technology"]
        candidate.target_roles = ["engineer"]
        candidate.target_locations = []

        dna = MagicMock()
        dna.embedding = None
        dna.experience_summary = "Python developer"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(candidate),
            _scalar(dna),
            _all_rows([]),
        ]

        valid_company = {
            "domain": "failco.com",
            "name": "FailCo",
            "reason": "...",
            "industry": "tech",
            "size": "51-200",
            "location": "NY",
            "tech_stack": [],
        }

        mock_openai = AsyncMock()
        mock_openai.parse_structured = AsyncMock(return_value={"companies": [valid_company]})

        mock_hunter = AsyncMock()
        mock_hunter.domain_search = AsyncMock(side_effect=Exception("Hunter API error"))

        with (
            patch("app.services.company_service.settings") as ms,
            patch("app.services.company_service.get_openai", return_value=mock_openai),
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
        ):
            ms.OPENAI_API_KEY = "sk-test"
            ms.HUNTER_API_KEY = "hunter-key"
            from app.services.company_service import discover_companies

            result = await discover_companies(mock_db, uuid.uuid4())

        # Result is empty - domain was skipped
        assert result == []


# ---------------------------------------------------------------------------
# add_company_manual - error branches
# ---------------------------------------------------------------------------


class TestAddCompanyManual:
    @pytest.mark.asyncio
    async def test_raises_when_company_already_exists(self):
        from app.services.company_service import add_company_manual

        existing = MagicMock()
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(existing)

        with pytest.raises(ValueError, match="already exists"):
            await add_company_manual(mock_db, uuid.uuid4(), "acme.com")

    @pytest.mark.asyncio
    async def test_creates_company_from_hunter_data(self):
        from app.services.company_service import add_company_manual

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(None),  # no existing company
            _scalar(None),  # no DNA
        ]

        hunter_data = {
            "organization": "Acme Corp",
            "description": "A great company",
            "industry": "technology",
            "size": "51-200",
            "location": "New York",
            "technologies": ["Python", "Docker"],
            "emails": [],
        }

        mock_hunter = AsyncMock()
        mock_hunter.domain_search = AsyncMock(return_value=hunter_data)

        mock_company = MagicMock()
        mock_company.id = uuid.uuid4()
        mock_company.domain = "acme.com"
        mock_company.status = "approved"

        with (
            patch("app.services.company_service.get_hunter", return_value=mock_hunter),
            patch("app.services.company_service.embed_text", new_callable=AsyncMock, return_value=[0.1, 0.2]),
            patch(
                "app.services.company_service._create_company_from_hunter",
                new_callable=AsyncMock,
                return_value=mock_company,
            ),
            patch("app.services.company_service._create_contacts_from_hunter", new_callable=AsyncMock, return_value=[]),
        ):
            result = await add_company_manual(mock_db, uuid.uuid4(), "acme.com")

        assert result.domain == "acme.com"
        assert result.status == "approved"


# ---------------------------------------------------------------------------
# approve_company / reject_company - edge cases
# ---------------------------------------------------------------------------


class TestApproveRejectCompany:
    @pytest.mark.asyncio
    async def test_approve_raises_when_company_not_found(self):
        from app.services.company_service import approve_company

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        with pytest.raises(ValueError, match="Company not found"):
            await approve_company(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_approve_raises_when_company_rejected(self):
        from app.models.enums import CompanyStatus
        from app.services.company_service import approve_company

        company = MagicMock()
        company.status = CompanyStatus.REJECTED

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(company)

        with pytest.raises(ValueError, match="Cannot approve a rejected"):
            await approve_company(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_reject_raises_when_company_not_found(self):
        from app.services.company_service import reject_company

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        with pytest.raises(ValueError, match="Company not found"):
            await reject_company(mock_db, uuid.uuid4(), "not a fit")

    @pytest.mark.asyncio
    async def test_reject_stores_reason_in_hunter_data(self):
        from app.services.company_service import reject_company

        company = MagicMock()
        company.status = "suggested"
        company.hunter_data = {}

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(company)

        result = await reject_company(mock_db, uuid.uuid4(), "culture mismatch")

        assert result.status == "rejected"
        assert result.hunter_data["rejection_reason"] == "culture mismatch"


# ---------------------------------------------------------------------------
# recalculate_fit_scores - edge cases
# ---------------------------------------------------------------------------


class TestRecalculateFitScores:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_dna(self):
        from app.services.company_service import recalculate_fit_scores

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        result = await recalculate_fit_scores(mock_db, uuid.uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_dna_has_no_embedding(self):
        from app.services.company_service import recalculate_fit_scores

        dna = MagicMock()
        dna.embedding = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(dna)

        result = await recalculate_fit_scores(mock_db, uuid.uuid4())

        assert result == 0

    @pytest.mark.asyncio
    async def test_updates_fit_scores_for_companies(self):
        from app.services.company_service import recalculate_fit_scores

        dna = MagicMock()
        dna.embedding = [0.1, 0.9]

        company = MagicMock()
        company.embedding = [0.2, 0.8]
        company.fit_score = 0.0

        dna_result = _scalar(dna)
        companies_result = MagicMock()
        companies_result.scalars.return_value.all.return_value = [company]

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [dna_result, companies_result]

        with patch("app.services.company_service.cosine_similarity", return_value=0.95):
            result = await recalculate_fit_scores(mock_db, uuid.uuid4())

        assert result == 1
        assert company.fit_score == 0.95
        mock_db.commit.assert_awaited_once()
