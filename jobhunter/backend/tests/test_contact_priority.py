"""Unit tests for company-size-aware contact priority helpers."""

from app.services.company_service import compute_contact_priority, get_company_size_tier


class TestGetCompanySizeTier:
    def test_small_range(self):
        assert get_company_size_tier("1-50") == "small"

    def test_medium_range(self):
        assert get_company_size_tier("51-200") == "medium"

    def test_large_range(self):
        assert get_company_size_tier("501-1000") == "large"

    def test_none_returns_medium(self):
        assert get_company_size_tier(None) == "medium"

    def test_empty_string_returns_medium(self):
        assert get_company_size_tier("") == "medium"

    def test_non_numeric_returns_medium(self):
        assert get_company_size_tier("startup") == "medium"

    def test_large_with_plus(self):
        assert get_company_size_tier("10000+") == "large"

    def test_single_number_small(self):
        assert get_company_size_tier("30") == "small"

    def test_whitespace_stripped(self):
        assert get_company_size_tier("  1-50  ") == "small"

    def test_boundary_50_is_small(self):
        assert get_company_size_tier("1-50") == "small"

    def test_boundary_51_is_medium(self):
        assert get_company_size_tier("51-200") == "medium"

    def test_boundary_500_is_medium(self):
        assert get_company_size_tier("201-500") == "medium"

    def test_boundary_501_is_large(self):
        assert get_company_size_tier("501-1000") == "large"


class TestComputeContactPriority:
    # CTO (hiring_manager) across company sizes
    def test_cto_small_company(self):
        role_type, is_dm, priority = compute_contact_priority("CTO", "small")
        assert role_type == "hiring_manager"
        assert is_dm is True
        assert priority == 3

    def test_cto_medium_company(self):
        role_type, is_dm, priority = compute_contact_priority("CTO", "medium")
        assert role_type == "hiring_manager"
        assert is_dm is True
        assert priority == 2

    def test_cto_large_company(self):
        role_type, is_dm, priority = compute_contact_priority("CTO", "large")
        assert role_type == "hiring_manager"
        assert is_dm is True
        assert priority == 1

    # Manager (team_lead) across company sizes
    def test_manager_small_company(self):
        role_type, is_dm, priority = compute_contact_priority("Engineering Manager", "small")
        assert role_type == "team_lead"
        assert is_dm is False
        assert priority == 2

    def test_manager_medium_company(self):
        role_type, is_dm, priority = compute_contact_priority("Engineering Manager", "medium")
        assert role_type == "team_lead"
        assert is_dm is False
        assert priority == 3

    def test_manager_large_company(self):
        role_type, is_dm, priority = compute_contact_priority("Engineering Manager", "large")
        assert role_type == "team_lead"
        assert is_dm is False
        assert priority == 2

    # Recruiter across company sizes
    def test_recruiter_small_company(self):
        role_type, is_dm, priority = compute_contact_priority("Technical Recruiter", "small")
        assert role_type == "recruiter"
        assert is_dm is False
        assert priority == 1

    def test_recruiter_medium_company(self):
        role_type, is_dm, priority = compute_contact_priority("Technical Recruiter", "medium")
        assert role_type == "recruiter"
        assert is_dm is False
        assert priority == 2

    def test_recruiter_large_company(self):
        role_type, is_dm, priority = compute_contact_priority("Technical Recruiter", "large")
        assert role_type == "recruiter"
        assert is_dm is False
        assert priority == 3

    # Other / unknown position
    def test_other_position(self):
        role_type, is_dm, priority = compute_contact_priority("Software Engineer", "medium")
        assert role_type == "other"
        assert is_dm is False
        assert priority == 0

    def test_empty_position(self):
        role_type, is_dm, priority = compute_contact_priority("", "medium")
        assert role_type == "other"
        assert is_dm is False
        assert priority == 0

    # VP of Recruiting — VP keyword matches hiring_manager first (order matters)
    def test_vp_of_recruiting_matches_hiring_manager(self):
        role_type, is_dm, _ = compute_contact_priority("VP of Recruiting", "medium")
        assert role_type == "hiring_manager"
        assert is_dm is True

    # Case insensitive checks
    def test_case_insensitive_director(self):
        role_type, is_dm, _ = compute_contact_priority("DIRECTOR OF ENGINEERING", "small")
        assert role_type == "hiring_manager"
        assert is_dm is True

    def test_case_insensitive_lead(self):
        role_type, is_dm, _ = compute_contact_priority("Tech Lead", "large")
        assert role_type == "team_lead"
        assert is_dm is False

    def test_case_insensitive_recruit(self):
        role_type, is_dm, _ = compute_contact_priority("RECRUITER", "large")
        assert role_type == "recruiter"
        assert is_dm is False

    # CEO and Head of X
    def test_ceo_is_hiring_manager(self):
        role_type, is_dm, _ = compute_contact_priority("CEO", "small")
        assert role_type == "hiring_manager"
        assert is_dm is True

    def test_head_of_product(self):
        role_type, is_dm, _ = compute_contact_priority("Head of Product", "medium")
        assert role_type == "hiring_manager"
        assert is_dm is True
