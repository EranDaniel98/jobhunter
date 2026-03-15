"""Unit tests for discovery validation helpers."""

from app.services.company_service import _parse_size_range, _validate_discovery_result


class TestParseSizeRange:
    def test_range_normal(self):
        assert _parse_size_range("51-200") == (51, 200)

    def test_range_with_plus(self):
        assert _parse_size_range("1000+") == (1000, 1000)

    def test_single_number(self):
        assert _parse_size_range("500") == (500, 500)

    def test_whitespace_stripped(self):
        assert _parse_size_range("  51-200  ") == (51, 200)

    def test_invalid_returns_none(self):
        assert _parse_size_range("startup") is None

    def test_empty_returns_none(self):
        assert _parse_size_range("") is None


class TestValidateDiscoveryResult:
    # --- No filters ---

    def test_no_filters_always_valid(self):
        company = {"name": "Acme", "size": "51-200", "location": "Berlin, Germany"}
        ok, reason = _validate_discovery_result(company, {})
        assert ok is True
        assert reason is None

    def test_no_filters_missing_fields_valid(self):
        company = {"name": "Acme"}
        ok, _reason = _validate_discovery_result(company, {})
        assert ok is True

    # --- Size checks ---

    def test_size_overlap_valid(self):
        # filter 51-200, company 101-300 → overlaps
        company = {"name": "Mid Corp", "size": "101-300", "location": ""}
        ok, reason = _validate_discovery_result(company, {"company_size": "51-200"})
        assert ok is True
        assert reason is None

    def test_size_exact_match_valid(self):
        company = {"name": "Mid Corp", "size": "51-200", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"company_size": "51-200"})
        assert ok is True

    def test_size_outside_filter_invalid(self):
        # filter 51-200, company 1000+ → no overlap
        company = {"name": "Big Corp", "size": "1000+", "location": ""}
        ok, reason = _validate_discovery_result(company, {"company_size": "51-200"})
        assert ok is False
        assert reason is not None
        assert "Big Corp" in reason

    def test_size_below_filter_invalid(self):
        # filter 201-500, company 1-10 → no overlap
        company = {"name": "Tiny Co", "size": "1-10", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"company_size": "201-500"})
        assert ok is False

    def test_size_missing_on_company_accepted(self):
        # missing size field → accepted (can't validate)
        company = {"name": "No Size Co", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"company_size": "51-200"})
        assert ok is True

    def test_size_empty_string_on_company_accepted(self):
        company = {"name": "No Size Co", "size": "", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"company_size": "51-200"})
        assert ok is True

    def test_size_unparseable_filter_accepted(self):
        # If the filter itself can't be parsed, overlap check is skipped
        company = {"name": "Some Co", "size": "startup", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"company_size": "startup"})
        assert ok is True

    # --- Location checks ---

    def test_location_match_valid(self):
        company = {"name": "Berlin Co", "size": "", "location": "Berlin, Germany"}
        ok, _reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": False})
        assert ok is True

    def test_location_case_insensitive(self):
        company = {"name": "Berlin Co", "size": "", "location": "berlin, germany"}
        ok, _reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": False})
        assert ok is True

    def test_location_no_match_invalid(self):
        company = {"name": "NYC Co", "size": "", "location": "New York, USA"}
        ok, reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": False})
        assert ok is False
        assert "NYC Co" in reason

    def test_location_missing_on_company_accepted(self):
        company = {"name": "No Loc Co", "size": ""}
        ok, _reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": False})
        assert ok is True

    def test_location_empty_string_on_company_accepted(self):
        company = {"name": "No Loc Co", "size": "", "location": ""}
        ok, _reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": False})
        assert ok is True

    def test_location_multiple_filters_partial_match(self):
        company = {"name": "Tel Aviv Co", "size": "", "location": "Tel Aviv, Israel"}
        ok, _reason = _validate_discovery_result(
            company,
            {"locations": ["Berlin", "Tel Aviv"], "includes_remote": False},
        )
        assert ok is True

    # --- Remote skips location check ---

    def test_remote_only_skips_location_check(self):
        # includes_remote=True with filter_locations → location check skipped
        company = {"name": "NYC Co", "size": "", "location": "New York, USA"}
        ok, _reason = _validate_discovery_result(company, {"locations": ["Berlin"], "includes_remote": True})
        assert ok is True

    def test_remote_no_physical_locations_valid(self):
        company = {"name": "Remote Co", "size": "51-200", "location": "Anywhere"}
        ok, _reason = _validate_discovery_result(company, {"locations": [], "includes_remote": True})
        assert ok is True

    # --- Combined size and location ---

    def test_size_valid_location_valid(self):
        company = {"name": "Good Co", "size": "51-200", "location": "Berlin, Germany"}
        ok, _reason = _validate_discovery_result(
            company,
            {"company_size": "51-200", "locations": ["Berlin"], "includes_remote": False},
        )
        assert ok is True

    def test_size_invalid_location_valid(self):
        # Size fails first, so result is False regardless of location
        company = {"name": "Big Co", "size": "5000+", "location": "Berlin, Germany"}
        ok, _reason = _validate_discovery_result(
            company,
            {"company_size": "51-200", "locations": ["Berlin"], "includes_remote": False},
        )
        assert ok is False

    def test_size_valid_location_invalid(self):
        company = {"name": "Wrong Loc Co", "size": "51-200", "location": "Tokyo, Japan"}
        ok, reason = _validate_discovery_result(
            company,
            {"company_size": "51-200", "locations": ["Berlin"], "includes_remote": False},
        )
        assert ok is False
        assert "Wrong Loc Co" in reason
