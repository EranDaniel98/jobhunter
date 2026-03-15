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
- **Medium**: upper bound 51-500
- **Large**: upper bound > 500
- **Unknown**: `size_range` is null or unparseable — default to medium

**Priority matrix:**

| Role | Small (1-50) | Medium (51-500) | Large (500+) |
|------|-------------|-----------------|--------------|
| CTO/CEO/VP/Director/Head | 3 | 2 | 1 |
| Manager/Lead | 2 | 3 | 2 |
| Recruiter | 1 | 2 | 3 |
| Other | 0 | 0 | 0 |

### Implementation
- Add `_get_company_size_tier(size_range: str | None) -> str` helper returning `"small"`, `"medium"`, or `"large"`
- Add `_compute_contact_priority(position: str, size_tier: str) -> tuple[str, bool, int]` returning `(role_type, is_decision_maker, priority)`
- Update `_create_contacts_from_hunter()` in `company_service.py` to use the new functions
- Update the duplicate logic in `contact_service.py` to use the same functions

### Parsing `size_range`
Extract the upper bound number from strings like "1-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000". If the string contains a dash, split and take the second number. If it's a single number, use that. If unparseable, return "medium".

---

## Fix 2: Block Analysis of Rejected Companies

### Problem
Users can approve and trigger research on a rejected company, consuming API quota for a company they already decided to skip.

### Solution
Add guards in two places:

1. **`approve_company` endpoint** (`app/api/companies.py`): If `company.status == "rejected"`, return HTTP 400 with message "Cannot approve a rejected company. Remove and re-discover it instead."

2. **`_research_background` function** (`app/api/companies.py`): At the start, reload the company from DB and check status. If rejected, log a warning and return early without calling the research graph.

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

Checks:
- **Size**: If `company_size` filter is set (e.g., "1-50"), parse both the filter and the returned company's `size` field. If ranges don't overlap, reject. Example: filter "1-50", company returns "201-500" — rejected. Filter "1-50", company returns "11-50" — accepted. If company size is missing/empty, accept (benefit of the doubt — Hunter.io will enrich later).
- **Location**: If `locations` filter is set, check if the company's returned `location` contains any of the requested locations (case-insensitive). Empty location from the company — accept. No location filter — accept.

### Flow
1. OpenAI returns N companies (typically 5-8)
2. Run `_validate_discovery_result()` on each
3. Collect valid companies
4. If valid count >= 3: proceed with valid companies only
5. If valid count < 3: retry OpenAI once with a reinforced prompt that explicitly lists what went wrong (e.g., "Your previous suggestions included companies with 500+ employees, but the user requires 1-50. Try again with ONLY companies matching the size requirement.")
6. After retry, validate again. Use whatever passes (even if < 3). No further retries.
7. Proceed to Hunter.io enrichment with the validated set

### Retry prompt
Append to the original prompt:
```
IMPORTANT CORRECTION: Your previous response included companies that did not match the filters.
Specifically: {list of violations}
Please suggest {count} replacement companies that STRICTLY match ALL criteria.
```

### Config
No new config vars needed. Max 1 retry is hardcoded — this is a bug fix, not a configurable feature.

### Logging
- `discovery.validation_filtered` — companies removed (detail: removed count, reasons)
- `discovery.validation_retry` — retrying due to insufficient valid results (detail: valid count, total count)

---

## Key Files

| Fix | Files |
|-----|-------|
| 1 | `app/services/company_service.py`, `app/services/contact_service.py` |
| 2 | `app/api/companies.py` |
| 3 | `app/services/company_service.py` |

## Testing
- `tests/test_contact_priority.py` (new) — unit tests for priority matrix across all size tiers
- `tests/test_discovery_validation.py` (new) — unit tests for size/location validation logic
- Existing `tests/test_companies.py` — add test for rejected company approve guard
