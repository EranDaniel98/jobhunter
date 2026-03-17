# Discovery & Contact Fixes Design Spec

**Date:** 2026-03-15
**Status:** Approved
**Scope:** 3 bug fixes — contact priority, rejected company guard, discovery validation

---

## Fix 1: Company-Size-Aware Contact Priority

### Problem
Contact outreach priority is static — CTO/CEO always gets priority 3 regardless of company size. Emailing a CTO at a 5,000-person company is inappropriate; emailing a recruiter at a 5-person company is a waste.

### Solution
Make priority depend on both role and company size tier.

**Size tiers** (derived from `Company.size_range` column, e.g., "1-50", "51-200"):
- **Small**: upper bound <= 50
- **Medium**: upper bound > 50 AND <= 500
- **Large**: upper bound > 500
- **Unknown**: `size_range` is null or unparseable — default to medium

**Priority matrix:**

| Role | Small (1-50) | Medium (51-500) | Large (501+) |
|------|-------------|-----------------|--------------|
| CTO/CEO/VP/Director/Head | 3 (decision_maker=True) | 2 (decision_maker=True) | 1 (decision_maker=True) |
| Manager/Lead | 2 (decision_maker=False) | 3 (decision_maker=False) | 2 (decision_maker=False) |
| Recruiter | 1 (decision_maker=False) | 2 (decision_maker=False) | 3 (decision_maker=False) |
| Other | 0 (decision_maker=False) | 0 (decision_maker=False) | 0 (decision_maker=False) |

`is_decision_maker` remains `True` only for CTO/CEO/VP/Director/Head regardless of company size — it indicates seniority, not outreach priority.

### Implementation

#### New helpers in `app/services/company_service.py`

- **`_get_company_size_tier(size_range: str | None) -> str`** — returns `"small"`, `"medium"`, or `"large"`. Parsing: split on `-`, take the second number as upper bound. Single number = use as-is. Unparseable/null = `"medium"`.
- **`_compute_contact_priority(position: str, size_tier: str) -> tuple[str, bool, int]`** — returns `(role_type, is_decision_maker, priority)`. The `position` parameter is the raw position string (will be lowercased internally). Role detection logic:
  - `"vp"`, `"director"`, `"head"`, `"cto"`, `"ceo"` in lowered position => `role_type="hiring_manager"`, `is_decision_maker=True`
  - `"manager"`, `"lead"` in lowered position => `role_type="team_lead"`, `is_decision_maker=False`
  - `"recruit"` in lowered position => `role_type="recruiter"`, `is_decision_maker=False`
  - Otherwise => `role_type="other"`, `is_decision_maker=False`, `priority=0` (regardless of size tier)

  These helpers must NOT be prefixed with `_` since they are imported externally. Use `get_company_size_tier` and `compute_contact_priority`.

#### Update `_create_contacts_from_hunter` (lines 429-480)

Current signature:
```python
async def _create_contacts_from_hunter(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    hunter_data: dict,
) -> list[Contact]:
```

The function needs the company's `size_range` to compute priorities. Two options:

**Option A (recommended):** Add a `size_range` parameter:
```python
async def _create_contacts_from_hunter(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    hunter_data: dict,
    size_range: str | None = None,
) -> list[Contact]:
```

Then compute `size_tier = get_company_size_tier(size_range)` once at the top, and replace the inline priority logic (lines 448-462) with:
```python
role_type, is_decision_maker, priority = compute_contact_priority(
    email_data.get("position") or "", size_tier
)
```

**Where to get `size_range` at each call site:**

1. **`add_company_manual`** (line 354): `hunter_data.get("size")` — the raw Hunter response has a `"size"` key (verified: `_create_company_from_hunter` reads `hunter_data.get("size")` on line 415).

2. **`create_contacts_node` in `app/graphs/company_research.py`** (line 313): The `hunter_data` is in state from `enrich_company_node`. But the company's `size_range` may also have been set from the DB. Best approach: query the Company record to get its current `size_range` (already set by `enrich_company_node` on line 91). This is a new DB query inside the graph node — add it before calling `_create_contacts_from_hunter`:
   ```python
   result = await db.execute(select(Company).where(Company.id == company_id))
   company = result.scalar_one_or_none()
   size_range = company.size_range if company else None
   ```

#### Update `find_contact` in `app/services/contact_service.py` (lines 42-56)

The function already loads the `Company` object (line 20-21). Use its `size_range`:
```python
size_tier = get_company_size_tier(company.size_range)
role_type, is_decision_maker, priority = compute_contact_priority(
    data.get("position") or "", size_tier
)
```

Import at the top of `contact_service.py`:
```python
from app.services.company_service import compute_contact_priority, get_company_size_tier
```

### Parsing `size_range`

Extract the upper bound number from strings like "1-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000". If the string contains a dash, split and take the second number. If it's a single number, use that. If unparseable, return "medium".

Edge cases to handle:
- `None` => "medium"
- `""` (empty string) => "medium"
- `"10000+"` => strip `+`, parse as 10000 => "large"
- `"1-50"` => 50 => "small"
- `"startup"` (non-numeric) => "medium"
- Whitespace: strip before parsing

### Downstream Impact

| Caller | File | Change needed |
|--------|------|---------------|
| `add_company_manual` | `app/services/company_service.py:354` | Pass `data.get("size")` as `size_range` |
| `create_contacts_node` | `app/graphs/company_research.py:313` | Query Company to get `size_range`, pass to function |
| `find_contact` | `app/services/contact_service.py:42-56` | Replace inline logic with shared helpers |
| `prioritize_contacts` | `app/services/contact_service.py:98-103` | No change needed (reads from DB, already stored priorities) |
| Contacts API responses | `app/api/contacts.py`, `app/api/companies.py:225-256` | No change needed (reads `outreach_priority` from DB) |
| Outreach service/graph | `app/services/outreach_service.py`, `app/graphs/outreach.py` | No change needed (does not reference `outreach_priority`) |
| Frontend `contacts-list.tsx` | `jobhunter/frontend/src/components/companies/contacts-list.tsx` | No change needed (displays priority from API) |

**Note on existing contacts:** This fix only affects newly created contacts. Existing contacts in the DB retain their old priorities. Consider a one-time migration script or a `recalculate_contact_priorities` function if retroactive updates are desired (out of scope for this fix).

---

## Fix 2: Block Analysis of Rejected Companies

### Problem
Users can approve and trigger research on a rejected company, consuming API quota for a company they already decided to skip.

### Solution
Add guards in three places:

1. **Primary guard in `company_service.py::approve_company()`** (line 362): Before changing status, check:
   ```python
   if company.status == CompanyStatus.REJECTED:
       raise ValueError("Cannot approve a rejected company")
   ```
   This requires importing `CompanyStatus` — currently NOT imported in `company_service.py`. Add:
   ```python
   from app.models.enums import CompanyStatus
   ```

2. **API error handling in `app/api/companies.py::approve_company()`** (lines 149-174): The current code does NOT catch `ValueError` from `company_service.approve_company()`. A `ValueError` will bubble up as a 500 Internal Server Error. Wrap the call:
   ```python
   try:
       company = await company_service.approve_company(db, company.id)
   except ValueError as e:
       raise safe_400(e, "Cannot approve this company") from e
   ```
   Note: `safe_400` is already imported (line 26). The safe_400 helper returns `HTTPException(status_code=400, detail=fallback)` where `fallback` is a sanitized message — the raw ValueError text is only logged, not exposed to the client.

3. **Defense-in-depth in `_research_background()`** (`app/api/companies.py`, line 375): At the start of Phase 1, after reloading the company from DB (line 381-383), add:
   ```python
   if company.status == CompanyStatus.REJECTED:
       logger.warning("research_skipped_rejected", company_id=str(company_id))
       return
   ```
   `CompanyStatus` is already imported in `companies.py` (line 11).

### Edge case: approve_company also needs "already approved" idempotency check
The current code on line 157-162 checks `old_status != CompanyStatus.APPROVED` to avoid re-triggering background tasks, but still calls `company_service.approve_company()` which redundantly commits. This is harmless but worth noting — the guard should only block `REJECTED`, not `APPROVED` re-approval.

### No frontend changes needed
The approve button should already be hidden for rejected companies. If not, disable it in the company card/detail view.

### Downstream Impact

| Caller | File | Change needed |
|--------|------|---------------|
| `approve_company` API | `app/api/companies.py:149-174` | Add try/except ValueError with safe_400 |
| `_research_background` | `app/api/companies.py:375-444` | Add rejected status guard after company reload |
| `company_service.approve_company` | `app/services/company_service.py:362-372` | Add CompanyStatus import + rejected guard |
| Tests | `tests/test_companies.py` | Add test: approve rejected company => 400 |

---

## Fix 3: Post-Processing Validation for Discovery Results

### Problem
OpenAI discovery returns companies that don't match the user's filters (wrong size, wrong location). The LLM treats `(STRICT)` as a suggestion, not a constraint.

### Solution
Add server-side validation after OpenAI returns results, before Hunter.io enrichment.

### Validation function
`_validate_discovery_result(company: dict, filters: dict) -> tuple[bool, str | None]`

Returns `(is_valid, violation_reason)`. The `company` dict uses OpenAI schema keys from `DISCOVERY_SCHEMA` — specifically `"size"` (not `"size_range"` which is the DB model column name), `"domain"`, `"name"`, `"industry"`.

The `filters` dict shape:
```python
{
    "company_size": "51-200",     # from discover_companies param, optional
    "locations": ["New York"],     # physical_locations (excluding "Remote"), optional
    "includes_remote": True,       # whether remote was in the original locations list
}
```

Checks:
- **Size**: If `company_size` filter is set (e.g., "51-200"), parse both the filter range and the company's `"size"` field into `[lower, upper]` integer pairs. Two ranges `[a1, b1]` and `[a2, b2]` overlap when `a1 <= b2 AND a2 <= b1`. If they don't overlap, reject. If company `"size"` is missing/empty/unparseable, accept (benefit of the doubt — Hunter.io will enrich later).
- **Location**: If `locations` filter is set (physical locations only — "Remote" is handled separately), check if the company's `"location"` field is present in the DISCOVERY_SCHEMA... **Wait — `"location"` is NOT in `DISCOVERY_SCHEMA`**. The schema only includes `"domain"`, `"name"`, `"reason"`, `"industry"`, `"size"`, `"tech_stack"`. To validate location, either:
  - **(a)** Add `"location"` to `DISCOVERY_SCHEMA` (requires schema change + prompt update), OR
  - **(b)** Skip location validation and rely on the prompt constraint

  **Recommendation:** Option (a) — add `"location": {"type": "string"}` to the schema items and add it to the `"required"` array. Then the prompt already asks for location implicitly; just update `DISCOVERY_SCHEMA` to capture it. Update the `DISCOVERY_PROMPT` to explicitly include: "For each company include its location (city, state/country)."

  With the schema updated, location validation becomes: case-insensitive substring match of any filter location against the company's `"location"` string. Empty/missing company location => accept. No location filter => accept. If `includes_remote` is True and there are no physical locations, skip location validation entirely.

### Implementation location

Add `_validate_discovery_result` in `app/services/company_service.py`, near the existing `discover_companies` function.

### Flow (modify `discover_companies` starting at line 303)

Current flow:
```
OpenAI returns suggestions -> iterate & Hunter enrich each -> commit
```

New flow:
```
OpenAI returns suggestions -> validate each -> if valid >= 3: proceed
                                             -> if valid < 3: retry OpenAI once with reinforced prompt
                                             -> validate retry results
                                             -> merge valid results (original + retry)
                                             -> iterate valid ones & Hunter enrich each -> commit
```

Insert validation between line 303 (`suggestions = await client.parse_structured(...)`) and line 306 (`for suggestion in suggestions.get("companies", []):`).

Detailed steps:
1. `raw_companies = suggestions.get("companies", [])`
2. Build filters dict from existing local variables: `company_size` (function param), `physical_locations` (already computed on line 257), `includes_remote` (already computed on line 258)
3. Run `_validate_discovery_result(c, filters)` on each, collecting valid companies and violation reasons
4. If valid count >= 3: proceed with valid companies only
5. If valid count < 3: retry OpenAI once with a reinforced prompt
6. After retry, validate again. Merge valid results from both attempts (deduplicate by domain). Use whatever passes (even if < 3). No further retries.
7. Replace `suggestions.get("companies", [])` with the validated list for the Hunter enrichment loop

### Retry prompt
Build a separate retry prompt string (NOT appended to `DISCOVERY_PROMPT.format()` — constructed independently to avoid brace-escaping issues with `DISCOVERY_PROMPT` which uses `.format()` with `{filter_instructions}`, `{candidate_summary}`, etc.):

```python
retry_prompt = (
    f"{original_formatted_prompt}\n\n"
    f"IMPORTANT CORRECTION: Your previous response included companies that did not match the filters.\n"
    f"Specifically: {'; '.join(violations)}\n"
    f"Please suggest {needed_count} replacement companies that STRICTLY match ALL criteria."
)
```

Where `original_formatted_prompt` is the already-formatted `prompt` variable (line 294-301) — an f-string on an already-formatted string, so no brace-escaping needed. `needed_count` should be the original target minus valid count (e.g., if 2 valid out of 6, request 4 more).

### Schema change required

Add `"location"` to `DISCOVERY_SCHEMA` (line 145-170):
```python
"properties": {
    "domain": {"type": "string"},
    "name": {"type": "string"},
    "reason": {"type": "string"},
    "industry": {"type": "string"},
    "size": {"type": "string"},
    "location": {"type": "string"},  # NEW
    "tech_stack": {
        "type": "array",
        "items": {"type": "string"},
    },
},
"required": ["domain", "name", "reason", "industry", "size", "location", "tech_stack"],
```

And update `DISCOVERY_PROMPT` (around line 141) to explicitly request location:
```
- For each company include its primary industry, approximate employee size range
  (e.g. "51-200", "201-500"), headquarters location (city, country), and known tech stack
```

### Config
No new config vars needed. Max 1 retry is hardcoded.

### Logging
- `discovery.validation_filtered` — companies removed (detail: removed count, reasons)
- `discovery.validation_retry` — retrying due to insufficient valid results (detail: valid count, total count)
- `discovery.validation_exhausted` — zero valid companies after retry (detail: total returned, all violations)

### Downstream Impact

| Caller | File | Change needed |
|--------|------|---------------|
| `discover_companies` | `app/services/company_service.py:214-335` | Add validation loop between OpenAI and Hunter enrichment |
| `DISCOVERY_SCHEMA` | `app/services/company_service.py:145-170` | Add `"location"` field |
| `DISCOVERY_PROMPT` | `app/services/company_service.py:117-143` | Add location to output format instruction |
| `_create_company_from_hunter` | `app/services/company_service.py:390-426` | No change — backfill logic on lines 320-325 still works (OpenAI suggestion now also has `"location"`, but `location_hq` is set from Hunter's `"location"` in `_create_company_from_hunter` on line 417) |
| API endpoint | `app/api/companies.py:49-78` | No change — same return shape |
| Frontend | No change — same `CompanyResponse` schema |
| OpenAI cost | Potential 1 extra API call per discovery run (retry). Rate limit on discover endpoint is already `2/hour` (line 50 of `companies.py`) which bounds cost |

---

## Key Files

| Fix | Files |
|-----|-------|
| 1 | `app/services/company_service.py` (`_create_contacts_from_hunter`, new `get_company_size_tier` + `compute_contact_priority` helpers), `app/services/contact_service.py` (`find_contact` — import shared helpers), `app/graphs/company_research.py` (`create_contacts_node` — pass `size_range`) |
| 2 | `app/services/company_service.py` (`approve_company` — add guard + import `CompanyStatus`), `app/api/companies.py` (`approve_company` — add try/except, `_research_background` — add guard) |
| 3 | `app/services/company_service.py` (`discover_companies` — add validation, `DISCOVERY_SCHEMA` — add location field, `DISCOVERY_PROMPT` — add location instruction, new `_validate_discovery_result`) |

## Testing
- `tests/test_contact_priority.py` (new) — unit tests for priority matrix across all size tiers and role types, including edge cases:
  - Null/empty/unparseable `size_range` defaults to medium
  - `"10000+"` format parses correctly
  - Whitespace handling
  - Position strings with multiple matching keywords (e.g., "VP of Recruiting" — should match VP first due to check order)
  - Empty position string => role_type "other", priority 0
- `tests/test_discovery_validation.py` (new) — unit tests for size/location validation logic, including:
  - Overlap algorithm with various range combos
  - Missing/empty company fields => accept (benefit of the doubt)
  - Location substring matching (case-insensitive)
  - Remote-only filter => skip location validation
  - Retry trigger: < 3 valid companies triggers retry
  - Retry merging: deduplication by domain across original + retry
  - All invalid after retry => return empty list (no crash)
- `tests/test_companies.py` — add tests:
  - Approve rejected company => 400 response
  - Approve suggested company => 200 (existing behavior, regression guard)
  - Approve already-approved company => 200 idempotent (no duplicate background tasks)
- `tests/test_company_research_graph.py` — update `create_contacts_node` tests to verify size-aware priority (if mocking `_create_contacts_from_hunter`, ensure `size_range` param is passed)
