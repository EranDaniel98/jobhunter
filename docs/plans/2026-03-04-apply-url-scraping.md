# Apply URL Scraping — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-scrape job posting content from a URL using Jina Reader API, replacing manual copy-paste in the Apply flow.

**Architecture:** New `POST /apply/scrape-url` endpoint calls Jina Reader API (`https://r.jina.ai/{url}`) via httpx, returns markdown text. Frontend sends URL → gets back auto-filled form fields (title, company, description). User reviews, then submits for analysis as before.

**Tech Stack:** httpx (already in deps), Jina Reader API (free, no key needed), OpenAI structured output (extract title/company from markdown)

---

### Task 1: Backend — URL Scraper Client

**Files:**
- Create: `jobhunter/backend/app/infrastructure/url_scraper.py`
- Test: `jobhunter/backend/tests/test_url_scraper.py`

**Step 1: Write the failing test**

```python
# tests/test_url_scraper.py
import pytest
import httpx

from app.infrastructure.url_scraper import scrape_job_url


class TestScrapeJobUrl:
    @pytest.mark.asyncio
    async def test_returns_markdown_on_success(self, monkeypatch):
        """Mocks httpx to return markdown, verifies scrape_job_url returns it."""
        fake_markdown = "# Senior Engineer\n\nWe are looking for..."

        async def mock_get(self, url, **kwargs):
            resp = httpx.Response(200, text=fake_markdown, request=httpx.Request("GET", url))
            return resp

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        result = await scrape_job_url("https://example.com/jobs/123")
        assert "Senior Engineer" in result
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            resp = httpx.Response(403, text="Forbidden", request=httpx.Request("GET", url))
            resp.raise_for_status()

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        with pytest.raises(Exception):
            await scrape_job_url("https://blocked.com/job")

    @pytest.mark.asyncio
    async def test_raises_on_empty_response(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(200, text="", request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        with pytest.raises(ValueError, match="empty"):
            await scrape_job_url("https://example.com/empty")
```

**Step 2: Run test to verify it fails**

Run: `cd jobhunter/backend && python -m pytest tests/test_url_scraper.py -v`
Expected: ImportError — `scrape_job_url` does not exist yet.

**Step 3: Write implementation**

```python
# app/infrastructure/url_scraper.py
import httpx
import structlog

logger = structlog.get_logger()

JINA_READER_BASE = "https://r.jina.ai"
TIMEOUT = 20.0  # Jina needs time to render JS


async def scrape_job_url(url: str) -> str:
    """Fetch a job posting URL via Jina Reader API and return clean markdown text."""
    jina_url = f"{JINA_READER_BASE}/{url}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(
            jina_url,
            headers={"Accept": "text/markdown"},
            follow_redirects=True,
        )
        response.raise_for_status()

    text = response.text.strip()
    if not text:
        raise ValueError("Scraping returned empty content for URL")

    logger.info("url_scraped", url=url, length=len(text))
    return text
```

**Step 4: Run tests to verify they pass**

Run: `cd jobhunter/backend && python -m pytest tests/test_url_scraper.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add jobhunter/backend/app/infrastructure/url_scraper.py jobhunter/backend/tests/test_url_scraper.py
git commit -m "feat: add Jina Reader URL scraper client"
```

---

### Task 2: Backend — Scrape URL Endpoint

**Files:**
- Modify: `jobhunter/backend/app/schemas/apply.py` — add request/response schemas
- Modify: `jobhunter/backend/app/api/apply.py` — add `POST /apply/scrape-url` endpoint
- Test: `jobhunter/backend/tests/test_apply.py` — add scrape endpoint tests

**Step 1: Add schemas**

Add to `app/schemas/apply.py`:

```python
class ScrapeUrlRequest(BaseModel):
    url: str

class ScrapeUrlResponse(BaseModel):
    raw_text: str
    title: str | None = None
    company_name: str | None = None
```

**Step 2: Add endpoint**

Add to `app/api/apply.py`:

```python
from app.schemas.apply import ScrapeUrlRequest, ScrapeUrlResponse

EXTRACT_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "company_name": {"type": "string"},
    },
    "required": ["title", "company_name"],
    "additionalProperties": False,
}


@router.post("/scrape-url", response_model=ScrapeUrlResponse)
@limiter.limit("20/day")
async def scrape_url(
    request: Request,
    req: ScrapeUrlRequest,
    candidate: Candidate = Depends(get_current_candidate),
):
    """Scrape a job posting URL and return the extracted text."""
    from app.infrastructure.url_scraper import scrape_job_url

    try:
        raw_text = await scrape_job_url(req.url)
    except Exception as e:
        logger.warning("scrape_url_failed", url=req.url, error=str(e))
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch job posting from URL. Please paste the description manually.",
        )

    # Try to extract title and company name from the first ~500 chars
    title = None
    company_name = None
    try:
        from app.dependencies import get_openai
        client = get_openai()
        snippet = raw_text[:2000]
        meta = await client.parse_structured(
            f"Extract the job title and company name from this job posting:\n\n{snippet}",
            "",
            EXTRACT_METADATA_SCHEMA,
        )
        title = meta.get("title") or None
        company_name = meta.get("company_name") or None
    except Exception:
        pass  # Metadata extraction is best-effort

    return ScrapeUrlResponse(raw_text=raw_text, title=title, company_name=company_name)
```

**Step 3: Write test**

Add to `tests/test_apply.py`:

```python
class TestScrapeUrlAPI:
    @pytest.mark.asyncio
    async def test_scrape_url_success(self, client, auth_headers, monkeypatch):
        fake_text = "# Senior Engineer at Acme\n\nWe need a Python developer..."

        async def mock_scrape(url):
            return fake_text

        monkeypatch.setattr("app.api.apply.scrape_job_url", mock_scrape)

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/scrape-url",
            json={"url": "https://example.com/job/123"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Senior Engineer" in data["raw_text"]

    @pytest.mark.asyncio
    async def test_scrape_url_failure_returns_422(self, client, auth_headers, monkeypatch):
        async def mock_scrape(url):
            raise RuntimeError("Connection refused")

        monkeypatch.setattr("app.api.apply.scrape_job_url", mock_scrape)

        resp = await client.post(
            f"{settings.API_V1_PREFIX}/apply/scrape-url",
            json={"url": "https://blocked.com/job"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "paste" in resp.json()["detail"].lower()
```

**Step 4: Run tests**

Run: `cd jobhunter/backend && python -m pytest tests/test_apply.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add jobhunter/backend/app/schemas/apply.py jobhunter/backend/app/api/apply.py jobhunter/backend/tests/test_apply.py
git commit -m "feat: add POST /apply/scrape-url endpoint with Jina Reader"
```

---

### Task 3: Frontend — Scrape API Function and Hook

**Files:**
- Modify: `jobhunter/frontend/src/lib/types.ts` — add `ScrapeUrlResponse` type
- Modify: `jobhunter/frontend/src/lib/api/apply.ts` — add `scrapeUrl()` function
- Modify: `jobhunter/frontend/src/lib/hooks/use-apply.ts` — add `useScrapeUrl()` mutation hook

**Step 1: Add type**

Add to `src/lib/types.ts` after the `ApplyAnalysisResponse` interface:

```typescript
export interface ScrapeUrlResponse {
  raw_text: string;
  title: string | null;
  company_name: string | null;
}
```

**Step 2: Add API function**

Add to `src/lib/api/apply.ts`:

```typescript
import type { ..., ScrapeUrlResponse } from "@/lib/types";

export async function scrapeUrl(url: string) {
  const { data } = await api.post<ScrapeUrlResponse>("/apply/scrape-url", { url });
  return data;
}
```

**Step 3: Add hook**

Add to `src/lib/hooks/use-apply.ts`:

```typescript
import * as applyApi from "@/lib/api/apply";

export function useScrapeUrl() {
  return useMutation({
    mutationFn: (url: string) => applyApi.scrapeUrl(url),
    onError: (err) => toastError(err, "Failed to fetch job posting"),
  });
}
```

**Step 4: Commit**

```bash
git add jobhunter/frontend/src/lib/types.ts jobhunter/frontend/src/lib/api/apply.ts jobhunter/frontend/src/lib/hooks/use-apply.ts
git commit -m "feat: add scrapeUrl API function and useScrapeUrl hook"
```

---

### Task 4: Frontend — Redesign Apply Form (URL-First)

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/apply/page.tsx` — rewrite the form section

**Goal:** URL field at top with "Fetch" button. On success: auto-fill title, company, description. Description shown as textarea (pre-filled, editable). Manual paste fallback if scraping fails.

**Step 1: Update the form**

Replace the form section inside `{showForm && (...)}` in `apply/page.tsx`.

Key changes:
1. Import `useScrapeUrl` hook
2. Add `scraping` state from the mutation
3. URL field at top with inline "Fetch" button
4. On fetch success: `setTitle(data.title)`, `setCompanyName(data.company_name)`, `setRawText(data.raw_text)`, show success toast
5. On fetch failure: show error toast, reveal empty description textarea
6. Description textarea always visible but pre-filled after fetch
7. `handleSubmit` validation: require either `rawText` (manual or scraped)
8. Remove "Saved for reference only" helper text from URL field — replace with "Paste URL and click Fetch to auto-fill"
9. Title field: no longer required in HTML (auto-filled from scrape), but still validated before submit

The form should look like:

```
┌─ New Job Analysis ──────────────────┐
│                                     │
│ Job URL                             │
│ [https://...              ] [Fetch] │
│ Paste a job posting URL to auto-    │
│ extract the description             │
│                                     │
│ ─── or fill manually ───            │
│                                     │
│ Job Title *                         │
│ [Senior Software Engineer     ]     │
│                                     │
│ Company Name                        │
│ [Acme Corp                    ]     │
│                                     │
│ Job Description *                   │
│ ┌──────────────────────────────┐    │
│ │ We are looking for a senior  │    │
│ │ engineer to join our team... │    │
│ └──────────────────────────────┘    │
│                                     │
│ [    Analyze Job Posting      ]     │
└─────────────────────────────────────┘
```

**Step 2: Implementation**

The main changes to the `ApplyPage` component:

1. Add `const scrapeMutation = useScrapeUrl();`
2. Add `handleFetch()` function that calls `scrapeMutation.mutate(url, { onSuccess: ... })`
3. Reorder form fields: URL first with Fetch button, then divider, then title/company/description
4. Auto-fill on fetch success
5. Update `handleSubmit` to not require title if rawText was scraped (actually keep title required — OpenAI extracts it)
6. The description `required` HTML attribute should be kept but validation done in JS

```tsx
function handleFetch() {
  if (!url.trim()) {
    toast.error("Enter a URL first");
    return;
  }
  scrapeMutation.mutate(url.trim(), {
    onSuccess: (data) => {
      setRawText(data.raw_text);
      if (data.title) setTitle(data.title);
      if (data.company_name) setCompanyName(data.company_name);
      toast.success("Job posting fetched successfully");
    },
  });
}
```

**Step 3: Commit**

```bash
git add jobhunter/frontend/src/app/\(dashboard\)/apply/page.tsx
git commit -m "feat: URL-first apply form with auto-fetch from job posting URL"
```

---

### Task 5: Integration Test and Final Polish

**Files:**
- Verify all existing tests still pass
- Manual smoke test the full flow

**Step 1: Run backend tests**

Run: `cd jobhunter/backend && python -m pytest tests/ -v --tb=short`
Expected: All pass

**Step 2: Run frontend type check**

Run: `cd jobhunter/frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Final commit with all changes**

If any fixups needed, commit them:

```bash
git add -A && git commit -m "chore: fixups for URL scraping feature"
```

---

## File Summary

| # | File | Action |
|---|------|--------|
| 1 | `backend/app/infrastructure/url_scraper.py` | CREATE |
| 2 | `backend/tests/test_url_scraper.py` | CREATE |
| 3 | `backend/app/schemas/apply.py` | MODIFY — add ScrapeUrlRequest/Response |
| 4 | `backend/app/api/apply.py` | MODIFY — add POST /apply/scrape-url |
| 5 | `backend/tests/test_apply.py` | MODIFY — add scrape endpoint tests |
| 6 | `frontend/src/lib/types.ts` | MODIFY — add ScrapeUrlResponse |
| 7 | `frontend/src/lib/api/apply.ts` | MODIFY — add scrapeUrl() |
| 8 | `frontend/src/lib/hooks/use-apply.ts` | MODIFY — add useScrapeUrl() |
| 9 | `frontend/src/app/(dashboard)/apply/page.tsx` | MODIFY — URL-first form |
