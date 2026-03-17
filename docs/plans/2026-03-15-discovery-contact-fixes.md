# Discovery & Contact Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 bugs: company-size-aware contact priority, block approving rejected companies, and post-process discovery results to filter non-matching companies.

**Architecture:** All fixes are in the backend service layer. Fix 1 adds two shared helpers and updates 3 call sites. Fix 2 adds guards at service + API layers. Fix 3 adds a validation function and retry logic in `discover_companies`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async

**Spec:** `docs/superpowers/specs/2026-03-15-discovery-contact-fixes-design.md`

---

## File Map

| Action | File |
|--------|------|
| Modify | `app/services/company_service.py` — add `get_company_size_tier`, `compute_contact_priority`, `_validate_discovery_result`; update `_create_contacts_from_hunter`, `approve_company`, `discover_companies`; update `DISCOVERY_SCHEMA` + `DISCOVERY_PROMPT` |
| Modify | `app/services/contact_service.py` — update `find_contact` to use shared helpers |
| Modify | `app/graphs/company_research.py` — update `create_contacts_node` to pass `size_range` |
| Modify | `app/api/companies.py` — add try/except in approve endpoint, add guard in `_research_background` |
| Create | `tests/test_contact_priority.py` — unit tests for priority matrix |
| Create | `tests/test_discovery_validation.py` — unit tests for validation logic |

---

## Chunk 1: Fix 1 — Company-Size-Aware Contact Priority

### Task 1: Priority helpers and tests

**Files:**
- Modify: `app/services/company_service.py`
- Create: `tests/test_contact_priority.py`

- [ ] **Step 1: Create tests for size tier parsing and priority computation**

Create `tests/test_contact_priority.py`:

```python
from app.services.company_service import get_company_size_tier, compute_contact_priority


class TestGetCompanySizeTier:
    def test_small(self):
        assert get_company_size_tier("1-50") == "small"
        assert get_company_size_tier("10-25") == "small"

    def test_medium(self):
        assert get_company_size_tier("51-200") == "medium"
        assert get_company_size_tier("201-500") == "medium"

    def test_large(self):
        assert get_company_size_tier("501-1000") == "large"
        assert get_company_size_tier("1001-5000") == "large"

    def test_none_defaults_medium(self):
        assert get_company_size_tier(None) == "medium"

    def test_empty_defaults_medium(self):
        assert get_company_size_tier("") == "medium"

    def test_unparseable_defaults_medium(self):
        assert get_company_size_tier("startup") == "medium"

    def test_plus_format(self):
        assert get_company_size_tier("10000+") == "large"

    def test_single_number(self):
        assert get_company_size_tier("30") == "small"
        assert get_company_size_tier("500") == "medium"
        assert get_company_size_tier("501") == "large"

    def test_whitespace(self):
        assert get_company_size_tier("  1-50  ") == "small"


class TestComputeContactPriority:
    # Small company: CTO=3, Manager=2, Recruiter=1
    def test_cto_small(self):
        role, dm, p = compute_contact_priority("CTO", "small")
        assert role == "hiring_manager"
        assert dm is True
        assert p == 3

    def test_manager_small(self):
        role, dm, p = compute_contact_priority("Engineering Manager", "small")
        assert role == "team_lead"
        assert dm is False
        assert p == 2

    def test_recruiter_small(self):
        role, dm, p = compute_contact_priority("Senior Recruiter", "small")
        assert role == "recruiter"
        assert dm is False
        assert p == 1

    # Medium company: Manager=3, CTO=2, Recruiter=2
    def test_cto_medium(self):
        _, _, p = compute_contact_priority("CTO", "medium")
        assert p == 2

    def test_manager_medium(self):
        _, _, p = compute_contact_priority("Team Lead", "medium")
        assert p == 3

    def test_recruiter_medium(self):
        _, _, p = compute_contact_priority("Technical Recruiter", "medium")
        assert p == 2

    # Large company: Recruiter=3, Manager=2, CTO=1
    def test_cto_large(self):
        _, _, p = compute_contact_priority("VP Engineering", "large")
        assert p == 1

    def test_manager_large(self):
        _, _, p = compute_contact_priority("Lead Developer", "large")
        assert p == 2

    def test_recruiter_large(self):
        _, _, p = compute_contact_priority("Talent Acquisition", "large")
        assert p == 0  # "Talent Acquisition" doesn't match "recruit"

    def test_recruiter_keyword_large(self):
        _, _, p = compute_contact_priority("Recruiter", "large")
        assert p == 3

    # Edge cases
    def test_empty_position(self):
        role, dm, p = compute_contact_priority("", "medium")
        assert role == "other"
        assert dm is False
        assert p == 0

    def test_vp_of_recruiting(self):
        # VP check comes first in order
        role, dm, p = compute_contact_priority("VP of Recruiting", "small")
        assert role == "hiring_manager"
        assert dm is True
        assert p == 3

    def test_case_insensitive(self):
        role, _, _ = compute_contact_priority("DIRECTOR of Engineering", "medium")
        assert role == "hiring_manager"
```

- [ ] **Step 2: Implement helpers in `company_service.py`**

Add after the imports, before the prompt constants (around line 15):

```python
def get_company_size_tier(size_range: str | None) -> str:
    """Determine company size tier from size_range string like '1-50', '501-1000'."""
    if not size_range:
        return "medium"
    s = size_range.strip().rstrip("+")
    try:
        if "-" in s:
            upper = int(s.split("-")[1].strip())
        else:
            upper = int(s)
    except (ValueError, IndexError):
        return "medium"
    if upper <= 50:
        return "small"
    if upper <= 500:
        return "medium"
    return "large"


PRIORITY_MATRIX = {
    "hiring_manager": {"small": 3, "medium": 2, "large": 1},
    "team_lead": {"small": 2, "medium": 3, "large": 2},
    "recruiter": {"small": 1, "medium": 2, "large": 3},
}


def compute_contact_priority(position: str, size_tier: str) -> tuple[str, bool, int]:
    """Compute (role_type, is_decision_maker, priority) from position and company size."""
    pos = position.lower()
    if any(t in pos for t in ["vp", "director", "head", "cto", "ceo"]):
        role_type = "hiring_manager"
        is_decision_maker = True
    elif any(t in pos for t in ["manager", "lead"]):
        role_type = "team_lead"
        is_decision_maker = False
    elif "recruit" in pos:
        role_type = "recruiter"
        is_decision_maker = False
    else:
        return "other", False, 0
    priority = PRIORITY_MATRIX[role_type][size_tier]
    return role_type, is_decision_maker, priority
```

- [ ] **Step 3: Run tests**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_contact_priority.py -xvs`

- [ ] **Step 4: Commit**

```bash
git add app/services/company_service.py tests/test_contact_priority.py
git commit -m "feat: add company-size-aware contact priority helpers"
```

---

### Task 2: Update call sites to use new helpers

**Files:**
- Modify: `app/services/company_service.py` — `_create_contacts_from_hunter`
- Modify: `app/services/contact_service.py` — `find_contact`
- Modify: `app/graphs/company_research.py` — `create_contacts_node`

- [ ] **Step 1: Update `_create_contacts_from_hunter` signature and logic**

In `app/services/company_service.py`, add `size_range` param and replace inline priority logic:

Change signature (line ~429):
```python
async def _create_contacts_from_hunter(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    hunter_data: dict,
    size_range: str | None = None,
) -> list[Contact]:
```

Replace lines 448-462 (the inline priority block) with:
```python
        role_type, is_decision_maker, priority = compute_contact_priority(
            email_data.get("position") or "", get_company_size_tier(size_range)
        )
```

- [ ] **Step 2: Update call site in `add_company_manual`**

In `app/services/company_service.py`, find where `_create_contacts_from_hunter` is called in `add_company_manual` (~line 354) and pass `size_range=hunter_data.get("size")`.

- [ ] **Step 3: Update `create_contacts_node` in `app/graphs/company_research.py`**

Read the file first. Find `create_contacts_node` and the call to `_create_contacts_from_hunter`. Before that call, query the company's size_range:

```python
company_result = await db.execute(select(Company).where(Company.id == company_id))
company_obj = company_result.scalar_one_or_none()
size_range = company_obj.size_range if company_obj else None
```

Then pass `size_range=size_range` to the function call. Make sure `Company` is imported.

- [ ] **Step 4: Update `find_contact` in `app/services/contact_service.py`**

Read `contact_service.py`. Add import at top:
```python
from app.services.company_service import compute_contact_priority, get_company_size_tier
```

In `find_contact` (lines 42-56), replace the inline priority logic with:
```python
size_tier = get_company_size_tier(company.size_range)
role_type, is_decision_maker, priority = compute_contact_priority(
    data.get("position") or "", size_tier
)
```

Note: check how the company object is loaded in this function (should already be available).

- [ ] **Step 5: Lint and format**

```bash
cd jobhunter/backend && uv run ruff check app/ --fix && uv run ruff format app/
```

- [ ] **Step 6: Commit**

```bash
git add app/services/company_service.py app/services/contact_service.py app/graphs/company_research.py
git commit -m "feat: use size-aware priority in all contact creation paths"
```

---

## Chunk 2: Fix 2 — Block Approving Rejected Companies

### Task 3: Add rejected company guard

**Files:**
- Modify: `app/services/company_service.py` — `approve_company`
- Modify: `app/api/companies.py` — approve endpoint + `_research_background`

- [ ] **Step 1: Add guard in `company_service.py::approve_company`**

Read the file. Add import if not present:
```python
from app.models.enums import CompanyStatus
```

In `approve_company` (line 362), add before `company.status = "approved"`:
```python
    if company.status == CompanyStatus.REJECTED:
        raise ValueError("Cannot approve a rejected company")
```

- [ ] **Step 2: Add try/except in API endpoint**

Read `app/api/companies.py`. In the `approve_company` endpoint, wrap the service call:
```python
    try:
        company = await company_service.approve_company(db, company.id)
    except ValueError as e:
        raise safe_400(e, "Cannot approve this company") from e
```

`safe_400` is already imported in the file.

- [ ] **Step 3: Add defense-in-depth in `_research_background`**

In `app/api/companies.py`, in `_research_background`, after reloading the company from DB, add:
```python
    if company.status == CompanyStatus.REJECTED:
        logger.warning("research_skipped_rejected", company_id=str(company_id))
        return
```

`CompanyStatus` is already imported in this file.

- [ ] **Step 4: Add test**

Add to `tests/test_companies.py`:
```python
@pytest.mark.asyncio
async def test_approve_rejected_company_returns_400(authenticated_client, db_session):
    """Approving a rejected company should return 400."""
    # Create a rejected company
    from app.models.company import Company
    company = Company(
        id=uuid.uuid4(),
        candidate_id=test_candidate_id,  # use existing fixture
        name="Rejected Corp",
        domain="rejected.com",
        status="rejected",
    )
    db_session.add(company)
    await db_session.commit()

    resp = await authenticated_client.post(f"/api/v1/companies/{company.id}/approve")
    assert resp.status_code == 400
```

Adapt this to match the existing test patterns in the file (check fixtures, auth headers, etc.).

- [ ] **Step 5: Lint and commit**

```bash
cd jobhunter/backend && uv run ruff check app/ --fix && uv run ruff format app/
git add app/services/company_service.py app/api/companies.py tests/test_companies.py
git commit -m "fix: block approving rejected companies with 400 response"
```

---

## Chunk 3: Fix 3 — Discovery Result Validation

### Task 4: Schema update and validation function

**Files:**
- Modify: `app/services/company_service.py` — `DISCOVERY_SCHEMA`, `DISCOVERY_PROMPT`, new `_validate_discovery_result`
- Create: `tests/test_discovery_validation.py`

- [ ] **Step 1: Create validation tests**

Create `tests/test_discovery_validation.py`:

```python
from app.services.company_service import _validate_discovery_result


class TestValidateDiscoveryResult:
    def test_no_filters_always_valid(self):
        company = {"name": "Acme", "size": "501-1000", "location": "NYC"}
        valid, reason = _validate_discovery_result(company, {})
        assert valid is True

    def test_size_overlap_valid(self):
        company = {"name": "Acme", "size": "11-50"}
        valid, _ = _validate_discovery_result(company, {"company_size": "1-50"})
        assert valid is True

    def test_size_no_overlap_invalid(self):
        company = {"name": "Acme", "size": "201-500"}
        valid, reason = _validate_discovery_result(company, {"company_size": "1-50"})
        assert valid is False
        assert "size" in reason.lower()

    def test_size_missing_accepted(self):
        company = {"name": "Acme"}
        valid, _ = _validate_discovery_result(company, {"company_size": "1-50"})
        assert valid is True

    def test_size_empty_accepted(self):
        company = {"name": "Acme", "size": ""}
        valid, _ = _validate_discovery_result(company, {"company_size": "1-50"})
        assert valid is True

    def test_location_match_valid(self):
        company = {"name": "Acme", "location": "Tel Aviv, Israel"}
        valid, _ = _validate_discovery_result(company, {"locations": ["Tel Aviv"]})
        assert valid is True

    def test_location_no_match_invalid(self):
        company = {"name": "Acme", "location": "San Francisco, USA"}
        valid, reason = _validate_discovery_result(company, {"locations": ["Tel Aviv"]})
        assert valid is False
        assert "location" in reason.lower()

    def test_location_case_insensitive(self):
        company = {"name": "Acme", "location": "tel aviv, israel"}
        valid, _ = _validate_discovery_result(company, {"locations": ["Tel Aviv"]})
        assert valid is True

    def test_location_missing_accepted(self):
        company = {"name": "Acme"}
        valid, _ = _validate_discovery_result(company, {"locations": ["NYC"]})
        assert valid is True

    def test_remote_only_skips_location(self):
        company = {"name": "Acme", "location": "Berlin, Germany"}
        valid, _ = _validate_discovery_result(
            company, {"locations": [], "includes_remote": True}
        )
        assert valid is True

    def test_both_size_and_location(self):
        company = {"name": "Acme", "size": "1-50", "location": "Tel Aviv"}
        valid, _ = _validate_discovery_result(
            company, {"company_size": "1-50", "locations": ["Tel Aviv"]}
        )
        assert valid is True

    def test_size_valid_location_invalid(self):
        company = {"name": "Acme", "size": "1-50", "location": "Berlin"}
        valid, _ = _validate_discovery_result(
            company, {"company_size": "1-50", "locations": ["Tel Aviv"]}
        )
        assert valid is False
```

- [ ] **Step 2: Update `DISCOVERY_SCHEMA` — add `location` field**

In `app/services/company_service.py`, find `DISCOVERY_SCHEMA` (around line 145). Add `"location": {"type": "string"}` to `properties` inside the items object, and add `"location"` to the `required` array.

- [ ] **Step 3: Update `DISCOVERY_PROMPT` — request location**

Find the instruction line about "primary industry, approximate employee size range" (around line 141). Change to:
```
- For each company include its primary industry, approximate employee size range
  (e.g. "51-200", "201-500"), headquarters location (city, country), and known tech stack
```

- [ ] **Step 4: Implement `_validate_discovery_result`**

Add in `app/services/company_service.py` near `discover_companies`:

```python
def _parse_size_range(size_str: str) -> tuple[int, int] | None:
    """Parse '1-50' or '500' into (lower, upper). Returns None if unparseable."""
    s = size_str.strip().rstrip("+")
    try:
        if "-" in s:
            parts = s.split("-")
            return int(parts[0].strip()), int(parts[1].strip())
        else:
            n = int(s)
            return n, n
    except (ValueError, IndexError):
        return None


def _validate_discovery_result(
    company: dict, filters: dict
) -> tuple[bool, str | None]:
    """Validate an OpenAI discovery suggestion against user filters."""
    # Size check
    filter_size = filters.get("company_size")
    if filter_size:
        company_size = company.get("size", "")
        if company_size:
            filter_range = _parse_size_range(filter_size)
            company_range = _parse_size_range(company_size)
            if filter_range and company_range:
                a1, b1 = filter_range
                a2, b2 = company_range
                if not (a1 <= b2 and a2 <= b1):
                    return False, f"{company.get('name', '?')} size {company_size} outside filter {filter_size}"

    # Location check
    filter_locations = filters.get("locations", [])
    includes_remote = filters.get("includes_remote", False)
    if filter_locations:
        company_location = company.get("location", "")
        if company_location:
            loc_lower = company_location.lower()
            if not any(fl.lower() in loc_lower for fl in filter_locations):
                return False, f"{company.get('name', '?')} location '{company_location}' not in {filter_locations}"
    elif includes_remote and not filter_locations:
        pass  # No physical location filter, skip

    return True, None
```

- [ ] **Step 5: Run tests**

Run: `cd jobhunter/backend && uv run python -m pytest tests/test_discovery_validation.py -xvs`

- [ ] **Step 6: Commit**

```bash
git add app/services/company_service.py tests/test_discovery_validation.py
git commit -m "feat: add discovery validation function and location to schema"
```

---

### Task 5: Integrate validation into `discover_companies`

**Files:**
- Modify: `app/services/company_service.py` — `discover_companies`

- [ ] **Step 1: Add validation loop after OpenAI call**

In `discover_companies`, after line 303 (`suggestions = await client.parse_structured(...)`) and before line 305 (`companies = []`), insert:

```python
    # Validate discovery results against filters
    raw_companies = suggestions.get("companies", [])
    filters = {
        "company_size": company_size,
        "locations": physical_locations,
        "includes_remote": includes_remote,
    }

    valid_companies = []
    violations = []
    for c in raw_companies:
        is_valid, reason = _validate_discovery_result(c, filters)
        if is_valid:
            valid_companies.append(c)
        else:
            violations.append(reason)

    if violations:
        logger.info("discovery.validation_filtered", extra={
            "detail": {"removed": len(violations), "reasons": violations},
        })

    # Retry once if fewer than 3 valid results
    if len(valid_companies) < 3 and violations:
        needed = 6 - len(valid_companies)  # request enough to hopefully get 3+
        retry_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT CORRECTION: Your previous response included companies that did not match the filters.\n"
            f"Specifically: {'; '.join(violations)}\n"
            f"Please suggest {needed} replacement companies that STRICTLY match ALL criteria."
        )
        logger.info("discovery.validation_retry", extra={
            "detail": {"valid_count": len(valid_companies), "total": len(raw_companies)},
        })
        retry_suggestions = await client.parse_structured(retry_prompt, "", DISCOVERY_SCHEMA)
        retry_companies = retry_suggestions.get("companies", [])
        existing_domains_in_valid = {c["domain"].strip().lower() for c in valid_companies}
        for c in retry_companies:
            is_valid, reason = _validate_discovery_result(c, filters)
            if is_valid and c["domain"].strip().lower() not in existing_domains_in_valid:
                valid_companies.append(c)
                existing_domains_in_valid.add(c["domain"].strip().lower())

    if not valid_companies:
        logger.warning("discovery.validation_exhausted", extra={
            "detail": {"total_returned": len(raw_companies), "violations": violations},
        })
```

Then replace the existing loop `for suggestion in suggestions.get("companies", []):` with `for suggestion in valid_companies:`.

- [ ] **Step 2: Lint and format**

```bash
cd jobhunter/backend && uv run ruff check app/ --fix && uv run ruff format app/
```

- [ ] **Step 3: Run full test suite**

```bash
cd jobhunter/backend && uv run python -m pytest tests/ -x -q --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add app/services/company_service.py
git commit -m "feat: validate discovery results against filters with retry"
```
