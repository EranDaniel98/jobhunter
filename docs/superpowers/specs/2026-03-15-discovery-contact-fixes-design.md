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

**Size tiers** (derived from `Company.size_range` field, e.g., "1-50", "51-200"):
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
- Add `_get_company_size_tier(size_range: str | None) -> str` helper returning `"small"`, `"medium"`, or `"large"`. Parsing: split on `-`, take the second number as upper bound. Single number = use as-is. Unparseable/null = `"medium"`.
- Add `_compute_contact_priority(position: str, size_tier: str) -> tuple[str, bool, int]` returning `(role_type, is_decision_maker, priority)`.
- Place both helpers in `app/services/company_service.py` (canonical location).
- Update `_create_contacts_from_hunter(db, candidate_id, company_id, hunter_data)` in `company_service.py`: extract `size_range` from `hunter_data.get("size")` (the Hunter.io API response includes company size), pass to `_get_company_size_tier()`, then use `_compute_contact_priority()` for each contact.
- Update `find_contact()` in `app/services/contact_service.py` (lines 42-56): import and use the same `_compute_contact_priority` from `company_service.py` instead of duplicating the logic. Pass the company's `size_range` from the `Company` object (available via the contact's `company_id` relationship or a separate query).

### Parsing `size_range`
Extract the upper bound number from strings like "1-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000". If the string contains a dash, split and take the second number. If it's a single number, use that. If unparseable, return "medium".

---

## Fix 2: Block Analysis of Rejected Companies

### Problem
Users can approve and trigger research on a rejected company, consuming API quota for a company they already decided to skip.

### Solution
Add guards in two places:

1. **Primary guard in `company_service.py::approve_company()`**: Before changing status, check `if company.status == CompanyStatus.REJECTED: raise ValueError("Cannot approve a rejected company")`. The API layer catches this and returns 400.

2. **Defense-in-depth in `_research_background()`** (`app/api/companies.py`): At the start, after reloading the company from DB, check `if company.status == CompanyStatus.REJECTED`. If so, log a warning and return early. This is a safety net for race conditions where a company is rejected between approval and background task execution.

Use `CompanyStatus.REJECTED` (StrEnum) for all comparisons — not bare string `"rejected"` — matching existing codebase patterns (e.g., `CompanyStatus.APPROVED` on line 162).

### No frontend changes needed
The approve button should already be hidden for rejected companies. If not, disable it in the company card/detail view.

---

## Fix 3: Post-Processing Validation for Discovery Results

### Problem
OpenAI discovery returns companies that don't match the user's filters (wrong size, wrong location). The LLM treats `(STRICT)` as a suggestion, not a constraint.

### Solution
Add server-side validation after OpenAI returns results, before Hunter.io enrichment.

### Validation function
`_validate_discovery_result(company: dict, filters: dict) -> bool`

The `company` dict uses OpenAI schema keys — specifically `"size"` (not `"size_range"` which is the DB model column name).

Checks:
- **Size**: If `company_size` filter is set (e.g., "1-50"), parse both the filter range and the company's `"size"` field into `[lower, upper]` integer pairs. Two ranges `[a1, b1]` and `[a2, b2]` overlap when `a1 <= b2 AND a2 <= b1`. If they don't overlap, reject. If company `"size"` is missing/empty/unparseable, accept (benefit of the doubt — Hunter.io will enrich later).
- **Location**: If `locations` filter is set, check if the company's `"location"` string contains any of the requested locations (case-insensitive substring match). Empty/missing location from the company — accept. No location filter — accept.

### Flow
1. OpenAI returns N companies (typically 5-8)
2. Run `_validate_discovery_result()` on each, collecting valid companies and violation reasons
3. If valid count >= 3: proceed with valid companies only
4. If valid count < 3: retry OpenAI once with a reinforced prompt
5. After retry, validate again. Use whatever passes (even if < 3). No further retries.
6. Proceed to Hunter.io enrichment with the validated set

### Retry prompt
Build a separate retry prompt string (NOT appended to `DISCOVERY_PROMPT.format()` — constructed independently to avoid brace-escaping issues):

```python
retry_prompt = (
    f"{original_formatted_prompt}\n\n"
    f"IMPORTANT CORRECTION: Your previous response included companies that did not match the filters.\n"
    f"Specifically: {'; '.join(violations)}\n"
    f"Please suggest {needed_count} replacement companies that STRICTLY match ALL criteria."
)
```

This uses an f-string directly — no `.format()` call, no brace-escaping needed.

### Config
No new config vars needed. Max 1 retry is hardcoded.

### Logging
- `discovery.validation_filtered` — companies removed (detail: removed count, reasons)
- `discovery.validation_retry` — retrying due to insufficient valid results (detail: valid count, total count)
- `discovery.validation_exhausted` — zero valid companies after retry (detail: total returned, all violations)

---

## Key Files

| Fix | Files |
|-----|-------|
| 1 | `app/services/company_service.py` (`_create_contacts_from_hunter`, new helpers), `app/services/contact_service.py` (`find_contact` — import shared helpers) |
| 2 | `app/services/company_service.py` (`approve_company`), `app/api/companies.py` (`_research_background`) |
| 3 | `app/services/company_service.py` (`discover_companies`, new `_validate_discovery_result`) |

## Testing
- `tests/test_contact_priority.py` (new) — unit tests for priority matrix across all size tiers and role types, including edge cases (null size, unparseable size, empty position)
- `tests/test_discovery_validation.py` (new) — unit tests for size/location validation logic, including overlap algorithm, missing fields, retry trigger threshold
- Existing `tests/test_companies.py` — add test for rejected company approve guard (assert 400 response)
