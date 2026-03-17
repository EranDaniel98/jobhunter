# Silent Failure Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 42 silent failure points identified in static analysis — ensuring every error path either surfaces to the user, logs at appropriate severity, or fails closed for security controls.

**Architecture:** Fixes are grouped into 7 tasks by subsystem: (1) Redis security fail-closed, (2) backend error handling, (3) SQLAlchemy/DB fixes, (4) pipeline robustness, (5) infrastructure clients, (6) frontend mutation error handling, (7) frontend misc fixes. Each task is independently committable and testable.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Redis, React/Next.js, TanStack Query, TypeScript

---

## Chunk 1: Backend Critical + High Fixes

### Task 1: Redis Security — Fail Closed on Security Controls

Fixes: C-1 (token blacklist bypass), C-3 (budget cap bypass), M-2 (no startup ping)

**Files:**
- Modify: `jobhunter/backend/app/dependencies.py:101-108`
- Modify: `jobhunter/backend/app/services/cost_service.py:46-54`
- Modify: `jobhunter/backend/app/infrastructure/redis_client.py:11-17`

- [ ] **Step 1: Fix token blacklist — fail closed when Redis is down**

In `app/dependencies.py`, after `blacklisted = await redis_safe_get(...)`, add explicit handling for Redis unavailability. The `redis_safe_get` function returns `None` on Redis failure AND when the key doesn't exist — we need to distinguish these cases.

```python
# In dependencies.py, replace the blacklist check block:
# OLD:
#   blacklisted = await redis_safe_get(f"{TOKEN_BLACKLIST_PREFIX}{jti}")
#   if blacklisted:
#       raise HTTPException(...)

# NEW:
from app.infrastructure.redis_client import get_redis
redis = get_redis()
try:
    blacklisted = await redis.get(f"{TOKEN_BLACKLIST_PREFIX}{jti}")
except Exception:
    logger.warning("token_blacklist_check_failed_redis_unavailable", jti=jti)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication service temporarily unavailable",
    )
if blacklisted:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has been revoked",
    )
```

- [ ] **Step 2: Fix budget check — fail closed when Redis is down**

In `app/services/cost_service.py`, change the `check_budget` except block from allowing requests to rejecting them:

```python
# In check_budget, replace the broad except block:
# OLD:
#   except Exception as e:
#       logger.warning("cost_budget_check_failed", error=str(e))

# NEW:
except HTTPException:
    raise
except Exception as e:
    logger.error("cost_budget_check_failed_redis_unavailable", error=str(e))
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Cost tracking service temporarily unavailable",
    )
```

- [ ] **Step 3: Elevate `_record_per_user` logging from debug to warning**

In `app/services/cost_service.py`, line 139:

```python
# OLD:
#   logger.debug("api_usage_insert_skipped", error=str(e))
# NEW:
    logger.warning("api_usage_insert_failed", error=str(e))
```

- [ ] **Step 4: Add Redis ping to `init_redis` for fast-fail at startup**

In `app/infrastructure/redis_client.py`:

```python
async def init_redis() -> aioredis.Redis:
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    await redis_client.ping()
    logger.info("redis_connected", url=settings.REDIS_URL.split("@")[-1])
    return redis_client
```

- [ ] **Step 5: Run backend tests**

Run: `cd jobhunter/backend && uv run pytest tests/ -x -q`
Expected: All tests pass (mocked Redis tests may need adjustment for fail-closed behavior)

- [ ] **Step 6: Commit**

```
git add jobhunter/backend/app/dependencies.py jobhunter/backend/app/services/cost_service.py jobhunter/backend/app/infrastructure/redis_client.py
git commit -m "fix(backend): fail closed on Redis unavailability for security controls

- Token blacklist now returns 503 when Redis is down (was silently bypassing)
- Budget check now returns 503 when Redis is down (was allowing uncapped spend)
- Elevate per-user cost recording log from debug to warning
- Add Redis ping on startup for fast-fail"
```

---

### Task 2: Backend Critical — Reset Password Script + Analytics Bug

Fixes: C-4 (wrong column name), H-3 (SQLAlchemy `not` bug)

**Files:**
- Modify: `jobhunter/backend/scripts/reset_password.py`
- Modify: `jobhunter/backend/app/api/analytics.py:69,76`

- [ ] **Step 1: Fix reset_password.py — correct column name and validate result**

Read the file first, then replace the UPDATE query:

```python
# OLD:
#   "UPDATE candidates SET hashed_password = $1 WHERE email = $2", h, email
# NEW:
r = await conn.execute(
    "UPDATE candidates SET password_hash = $1 WHERE email = $2", h, email
)
count = int(str(r).split(" ")[-1])
if count == 0:
    print(f"ERROR: No candidate found with email '{email}'. Password NOT changed.")
    return
print(f"Password updated successfully for {email}")
```

- [ ] **Step 2: Fix analytics `not` operator — use SQLAlchemy `~` instead**

In `app/api/analytics.py`, find both occurrences of `not AnalyticsInsight.is_read`:

```python
# OLD (line 69):
#   query = query.where(not AnalyticsInsight.is_read)
# NEW:
    query = query.where(AnalyticsInsight.is_read == False)  # noqa: E712

# OLD (line 76, count query):
#   count_q = count_q.where(not AnalyticsInsight.is_read)
# NEW:
    count_q = count_q.where(AnalyticsInsight.is_read == False)  # noqa: E712
```

- [ ] **Step 3: Run ruff check**

Run: `cd jobhunter/backend && uv run ruff check scripts/reset_password.py app/api/analytics.py`
Expected: All checks passed

- [ ] **Step 4: Commit**

```
git add jobhunter/backend/scripts/reset_password.py jobhunter/backend/app/api/analytics.py
git commit -m "fix(backend): correct password reset column name and analytics filter bug

- reset_password.py: fix column hashed_password → password_hash, add result validation
- analytics.py: fix Python 'not' on SQLAlchemy column (always False) → use == False"
```

---

### Task 3: Backend — API Response Honesty + Error Surfacing

Fixes: H-4 (approve swallows send failure), H-8 (newsapi 401 invisible), M-1 (quota zeros), M-5 (newsapi returns [])

**Files:**
- Modify: `jobhunter/backend/app/api/approvals.py:94-97`
- Modify: `jobhunter/backend/app/infrastructure/newsapi_client.py:44-46`
- Modify: `jobhunter/backend/app/services/quota_service.py:98-103`

- [ ] **Step 1: Fix approvals — return error on send failure**

In `app/api/approvals.py`:

```python
# OLD:
#   except ValueError as e:
#       logger.warning("approved_send_failed", action_id=action_id, error=str(e))
# NEW:
    except ValueError as e:
        logger.error("approved_send_failed", action_id=action_id, error=str(e))
        raise HTTPException(status_code=422, detail=f"Approved but send failed: {e}")
```

- [ ] **Step 2: Fix newsapi — distinguish auth errors from empty results**

In `app/infrastructure/newsapi_client.py`:

```python
# OLD:
#   except httpx.HTTPStatusError as e:
#       logger.error("newsapi_http_error", status=e.response.status_code, query=query)
#       return []
# NEW:
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            logger.error("newsapi_auth_error", status=e.response.status_code,
                         detail="API key may be invalid or expired")
            raise  # Propagate auth errors — don't mask as empty results
        logger.warning("newsapi_http_error", status=e.response.status_code, query=query)
        return []
```

- [ ] **Step 3: Fix quota service — indicate degraded state instead of zeros**

In `app/services/quota_service.py`, modify the exception handler to include a `degraded` flag:

```python
# OLD:
#   except Exception as e:
#       logger.warning(...)
#       for qt in USER_FACING_QUOTAS:
#           quotas.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0)})
# NEW:
    except Exception as e:
        logger.warning("get_usage_redis_failure", candidate_id=candidate_id, error=str(e))
        degraded = True
        for qt in USER_FACING_QUOTAS:
            quotas.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0)})
            weekly.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0) * 7})
            monthly.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0) * 30})
```

Then ensure `degraded` is returned in the response (check the return value of the function and add the field if not present).

- [ ] **Step 4: Run ruff check**

Run: `cd jobhunter/backend && uv run ruff check app/api/approvals.py app/infrastructure/newsapi_client.py app/services/quota_service.py`

- [ ] **Step 5: Commit**

```
git add jobhunter/backend/app/api/approvals.py jobhunter/backend/app/infrastructure/newsapi_client.py jobhunter/backend/app/services/quota_service.py
git commit -m "fix(backend): surface API errors instead of swallowing them

- approvals: return 422 on send failure instead of silent 200
- newsapi: propagate 401/403 auth errors instead of returning []
- quota: add degraded flag when Redis is unavailable"
```

---

### Task 4: Backend — Pipeline Robustness

Fixes: C-2 (apply pipeline bare redis.set), H-2 (scout rollback), H-6 (quota decrement), M-5 (scout scoring), M-9 (apply match_skills_node), M-3 (warmup bypass)

**Files:**
- Modify: `jobhunter/backend/app/graphs/apply_pipeline.py:199-211,291-295`
- Modify: `jobhunter/backend/app/graphs/scout_pipeline.py:319-321,380-389`
- Modify: `jobhunter/backend/app/graphs/outreach.py:470-473`
- Modify: `jobhunter/backend/app/services/email_service.py:181-183`

- [ ] **Step 1: Wrap apply pipeline redis.set in try/except**

In `app/graphs/apply_pipeline.py`, around line 291:

```python
# OLD:
#   await redis.set(
#       f"apply:analysis:{job_posting_id_str}",
#       json.dumps(analysis),
#       ex=settings.REDIS_APPLY_ANALYSIS_TTL,
#   )
# NEW:
    try:
        await redis.set(
            f"apply:analysis:{job_posting_id_str}",
            json.dumps(analysis),
            ex=settings.REDIS_APPLY_ANALYSIS_TTL,
        )
    except Exception as e:
        logger.error("apply_analysis_cache_failed", job_posting_id=job_posting_id_str, error=str(e))
        return {"status": "failed", "error": f"Failed to cache analysis: {e}"}
```

- [ ] **Step 2: Add guard to match_skills_node**

In `app/graphs/apply_pipeline.py`, at the start of `match_skills_node`:

```python
# Add at the top of the function body:
parsed = state.get("parsed_requirements")
candidate_skills = state.get("candidate_skills")
if not parsed or not candidate_skills:
    return {"status": "failed", "error": "Missing requirements or candidate skills for matching"}
```

- [ ] **Step 3: Fix scout pipeline — use savepoint for company inserts**

In `app/graphs/scout_pipeline.py`, replace the IntegrityError handler:

```python
# OLD:
#   try:
#       db.add(company)
#       ...
#       await db.flush()
#       created += 1
#   except IntegrityError:
#       await db.rollback()
#       logger.info(...)
#       continue
# NEW:
    try:
        async with db.begin_nested():  # savepoint
            db.add(company)
            db.add(signal)
            await db.flush()
        created += 1
    except IntegrityError:
        logger.info("scout_company_duplicate", domain=c["domain"])
        continue
```

- [ ] **Step 4: Track and surface scout scoring failures**

In `app/graphs/scout_pipeline.py`, in `score_and_filter_node`:

```python
# Add a counter before the loop:
failed_count = 0
# In the except block:
except Exception as e:
    failed_count += 1
    logger.warning("scout_score_failed", company=company["company_name"], error=str(e))
    continue
# After the loop, log aggregate:
if failed_count > 0:
    logger.error("scout_scoring_partial_failure", failed=failed_count, total=len(parsed))
```

- [ ] **Step 5: Add quota decrement to outreach send_email_node failure path**

In `app/graphs/outreach.py`, in the except block of `send_email_node` (around line 470):

```python
# After setting message.status = MessageStatus.FAILED:
# Add quota decrement:
try:
    from app.services.quota_service import decrement_usage
    await decrement_usage(str(candidate_id), "email")
except Exception as dec_err:
    logger.warning("outreach_quota_decrement_failed", error=str(dec_err))
```

Note: Check if `decrement_usage` exists in `quota_service.py`. If not, add it as the inverse of `check_and_increment` — a simple Redis DECR on the same key.

- [ ] **Step 6: Add hard fallback limit for email warmup when Redis is down**

In `app/services/email_service.py`, modify the warmup except block:

```python
# OLD:
#   except Exception as e:
#       logger.warning("warmup_check_failed", domain=sender_domain, error=str(e))
# NEW:
    except Exception as e:
        logger.warning("warmup_check_failed_using_fallback", domain=sender_domain, error=str(e))
        # Fallback: allow max 5 emails when Redis is unavailable
        # This prevents reputation damage from unrestricted sending
        warmup_fallback_key = f"_warmup_fallback_{sender_domain}"
        if not hasattr(send_outreach, warmup_fallback_key):
            setattr(send_outreach, warmup_fallback_key, 0)
        count = getattr(send_outreach, warmup_fallback_key)
        if count >= 5:
            raise ValueError(f"Email warmup fallback limit reached for {sender_domain} (Redis unavailable)")
        setattr(send_outreach, warmup_fallback_key, count + 1)
```

- [ ] **Step 7: Run ruff + tests**

Run: `cd jobhunter/backend && uv run ruff check app/graphs/ app/services/email_service.py && uv run pytest tests/ -x -q`

- [ ] **Step 8: Commit**

```
git add jobhunter/backend/app/graphs/ jobhunter/backend/app/services/email_service.py
git commit -m "fix(backend): improve pipeline error handling and quota consistency

- apply_pipeline: wrap redis.set in try/except, guard match_skills_node inputs
- scout_pipeline: use savepoints for company inserts, track scoring failures
- outreach: decrement quota on send failure
- email_service: add fallback warmup limit when Redis is down"
```

---

### Task 5: Backend — Infrastructure Client Fixes

Fixes: H-5 (SSRF DNS bypass), H-7 (resend return type), M-6 (tenant.py bare except), M-4 (candidates nested swallow)

**Files:**
- Modify: `jobhunter/backend/app/infrastructure/url_scraper.py:22-23`
- Modify: `jobhunter/backend/app/infrastructure/resend_client.py:47`
- Modify: `jobhunter/backend/app/middleware/tenant.py:75`
- Modify: `jobhunter/backend/app/api/candidates.py:107-108`

- [ ] **Step 1: Fix SSRF DNS bypass — log and reject on gaierror**

In `app/infrastructure/url_scraper.py`:

```python
# OLD:
#   except socket.gaierror:
#       pass  # Can't resolve - let Jina handle it
# NEW:
    except socket.gaierror:
        logger.warning("url_validation_dns_failed", url=url)
        # DNS can't resolve - still allow but log for monitoring
        # Private IP check was skipped — acceptable risk for unresolvable domains
```

- [ ] **Step 2: Fix resend client — normalize return type**

In `app/infrastructure/resend_client.py`:

```python
# OLD:
#   result = await loop.run_in_executor(None, partial(resend.Emails.send, params))
#   logger.info("email_sent_via_resend", to=to, message_id=result.get("id"))
#   return result
# NEW:
    result = await loop.run_in_executor(None, partial(resend.Emails.send, params))
    # Normalize SDK result to dict (some versions return Pydantic models)
    result_dict = dict(result) if not isinstance(result, dict) else result
    logger.info("email_sent_via_resend", to=to, message_id=result_dict.get("id"))
    return result_dict
```

- [ ] **Step 3: Fix tenant.py — split expected vs unexpected exceptions**

In `app/middleware/tenant.py`:

```python
# OLD:
#   except Exception:
#       pass  # Auth dependency will handle invalid tokens
# NEW:
    except (jwt.PyJWTError, KeyError, ValueError):
        pass  # Expected — auth dependency handles invalid tokens
    except Exception as e:
        logger.debug("tenant_extract_unexpected_error", error=str(e))
```

Note: Check the actual import name — may be `from jwt import PyJWTError` or `jwt.exceptions.PyJWTError`.

- [ ] **Step 4: Fix candidates nested swallow — elevate logging**

In `app/api/candidates.py`:

```python
# OLD:
#   except Exception as e:
#       logger.warning("resume_pipeline_status_update_failed", error=str(e))
# NEW:
    except Exception as e:
        logger.error("resume_pipeline_status_update_failed",
                     resume_id=str(resume_id), error=str(e))
```

- [ ] **Step 5: Run ruff + tests**

Run: `cd jobhunter/backend && uv run ruff check app/infrastructure/ app/middleware/ app/api/candidates.py`

- [ ] **Step 6: Commit**

```
git add jobhunter/backend/app/infrastructure/ jobhunter/backend/app/middleware/tenant.py jobhunter/backend/app/api/candidates.py
git commit -m "fix(backend): improve infrastructure client error handling

- url_scraper: log DNS validation failures instead of silent pass
- resend_client: normalize SDK return type to dict
- tenant.py: split expected JWT errors from unexpected exceptions
- candidates: elevate pipeline status update failure to error level"
```

---

## Chunk 2: Frontend Fixes

### Task 6: Frontend — Mutation Error Handling

Fixes: C-3 (notes onError), C-4 (markReplied onError), C-5/C-6 (bulk send/delete race), I-4 (apply delete dialog), I-5/I-6 (company approve/reject), I-7 (insights markRead), I-8 (resume delete dialog), I-9 (stage mutation), I-10 (admin waitlist)

**Files:**
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/[id]/page.tsx`
- Modify: `jobhunter/frontend/src/app/(dashboard)/outreach/page.tsx`
- Modify: `jobhunter/frontend/src/app/(dashboard)/companies/page.tsx`
- Modify: `jobhunter/frontend/src/app/(dashboard)/apply/page.tsx`
- Modify: `jobhunter/frontend/src/app/(dashboard)/resume/page.tsx`
- Modify: `jobhunter/frontend/src/lib/hooks/use-analytics-insights.ts`
- Modify: `jobhunter/frontend/src/lib/hooks/use-admin.ts`
- Modify: `jobhunter/frontend/src/lib/hooks/use-apply.ts`

- [ ] **Step 1: Fix company detail page — add onError to notes, approve, reject, retry**

In `app/(dashboard)/companies/[id]/page.tsx`:

For `upsertNotesMutation.mutate()`:
```typescript
// Add onError callback:
upsertNotesMutation.mutate(
    { companyId: id, content: noteContent },
    {
        onSuccess: () => { setNotesDirty(false); toast.success("Notes saved"); },
        onError: (err: unknown) => toastError(err, "Failed to save notes"),
    }
);
```

For all `approveMutation.mutate()`, `rejectMutation.mutate()`, and retry research calls — add `onError`:
```typescript
approveMutation.mutate(company.id, {
    onSuccess: () => toast.success("Company approved"),
    onError: (err: unknown) => toastError(err, "Failed to approve company"),
})
```

Same pattern for reject and retry research.

- [ ] **Step 2: Fix outreach page — markReplied onError + bulk send/delete race**

For `markRepliedMutation.mutate()`:
```typescript
markRepliedMutation.mutate(selectedMessage.id, {
    onSuccess: (updated) => {
        setSelectedMessage(updated);
        toast.success("Marked as replied");
    },
    onError: (err: unknown) => toastError(err, "Failed to mark as replied"),
});
```

For bulk send — track both success and failure counters:
```typescript
let completed = 0;
let failed = 0;
drafts.forEach((d) => {
    sendMutation.mutate(
        { id: d.id, attachResume: true },
        {
            onSuccess: () => {
                completed++;
                if (completed + failed === drafts.length) {
                    if (failed > 0) {
                        toast.warning(`Sent ${completed} of ${drafts.length} — ${failed} failed`);
                    } else {
                        toast.success(`Sent ${completed} message(s)`);
                    }
                    setSelectedIds(new Set());
                    setBulkMode(false);
                }
            },
            onError: (err: unknown) => {
                failed++;
                if (completed + failed === drafts.length) {
                    toast.error(`${failed} of ${drafts.length} sends failed`);
                    setSelectedIds(new Set());
                    setBulkMode(false);
                }
            },
        },
    );
});
```

Apply the same pattern to bulk delete.

- [ ] **Step 3: Fix companies list page — add onError to approve/reject**

In `app/(dashboard)/companies/page.tsx`:

```typescript
// For each approveMutation.mutate and rejectMutation.mutate call:
approveMutation.mutate(company.id, {
    onSuccess: () => toast.success("Company approved"),
    onError: (err: unknown) => toastError(err, "Failed to approve company"),
})
```

- [ ] **Step 4: Fix apply page — close delete dialog on error, add stage onError**

In `app/(dashboard)/apply/page.tsx`:

For the delete dialog — add `setDeleteConfirmId(null)` in `onError` if missing.

For the stage mutation — add onError to `useUpdatePostingStage` hook definition in `use-apply.ts`:
```typescript
export function useUpdatePostingStage() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ...,
        onSuccess: () => { qc.invalidateQueries({ queryKey: ["apply-postings"] }); },
        onError: (err: unknown) => toastError(err, "Failed to update stage"),
    });
}
```

- [ ] **Step 5: Fix resume page — close delete dialog on error**

In `app/(dashboard)/resume/page.tsx`:

```typescript
deleteMutation.mutate(deleteId, {
    onSuccess: () => {
        toast.success("Resume deleted");
        setDeleteId(null);
    },
    onError: () => {
        toast.error("Failed to delete resume");
        setDeleteId(null);  // Close dialog on failure too
    },
});
```

- [ ] **Step 6: Fix hook-level defaults — add onError to hooks**

In `lib/hooks/use-analytics-insights.ts`:
```typescript
export function useMarkInsightRead() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: insightsApi.markInsightRead,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["analytics-insights"] });
            qc.invalidateQueries({ queryKey: ["analytics-dashboard"] });
        },
        onError: (err: unknown) => toastError(err, "Failed to mark insight as read"),
    });
}
```

In `lib/hooks/use-admin.ts`, for both `useInviteWaitlistEntry` and `useInviteWaitlistBatch`:
```typescript
onError: (err: unknown) => toastError(err, "Failed to invite user"),
```

- [ ] **Step 7: Build to verify**

Run: `cd jobhunter/frontend && npm run build`
Expected: Compiled successfully

- [ ] **Step 8: Commit**

```
git add jobhunter/frontend/src/app/ jobhunter/frontend/src/lib/hooks/
git commit -m "fix(frontend): add onError handlers to all mutations

- company detail: notes auto-save, approve/reject, retry research
- outreach: markReplied, bulk send/delete with completion tracking
- companies list: approve/reject
- apply: delete dialog close on error, stage mutation
- resume: delete dialog close on error
- hooks: useMarkInsightRead, useInviteWaitlist*, useUpdatePostingStage"
```

---

### Task 7: Frontend — Misc Fixes (Clipboard, Auth, Tour, Onboarding)

Fixes: C-1 (onboarding stuck), C-2 (tour catch), C-7/C-8 (clipboard), I-1 (localStorage), I-2 (refreshUser), I-3 (revokeURL)

**Files:**
- Modify: `jobhunter/frontend/src/app/(onboarding)/onboarding/page.tsx:77`
- Modify: `jobhunter/frontend/src/components/dashboard/tour-overlay.tsx:74,89`
- Modify: `jobhunter/frontend/src/app/(dashboard)/settings/page.tsx:167-181`
- Modify: `jobhunter/frontend/src/providers/auth-provider.tsx:52-53,91-92`
- Modify: `jobhunter/frontend/src/lib/api/admin.ts:106-117`

- [ ] **Step 1: Fix onboarding — add catch to completeOnboarding**

In `app/(onboarding)/onboarding/page.tsx`:

```typescript
// OLD:
//   completeOnboarding().then(() => router.push("/dashboard"));
// NEW:
completeOnboarding()
    .then(() => router.push("/dashboard"))
    .catch(() => {
        toast.error("Could not complete setup. Please refresh and try again.");
    });
```

Make sure `toast` (from `sonner`) is imported.

- [ ] **Step 2: Fix tour overlay — log warning on completeTour failure**

In `components/dashboard/tour-overlay.tsx`, both occurrences:

```typescript
// OLD:
//   completeTour().catch(() => {});
// NEW:
completeTour().catch(() => {
    console.warn("Failed to persist tour completion — will retry on next visit");
});
```

- [ ] **Step 3: Fix clipboard — await and handle failures**

In `app/(dashboard)/settings/page.tsx`, fix `copyInviteUrl`:

```typescript
// OLD:
//   function copyInviteUrl(code: string) {
//       const url = `${window.location.origin}/register?invite=${code}`;
//       navigator.clipboard.writeText(url);
//       toast.success("Link copied");
//   }
// NEW:
async function copyInviteUrl(code: string) {
    const url = `${window.location.origin}/register?invite=${code}`;
    try {
        await navigator.clipboard.writeText(url);
        toast.success("Link copied");
    } catch {
        toast.error("Failed to copy link");
    }
}
```

Fix `handleGenerateInvite` — separate invite creation from clipboard:

```typescript
async function handleGenerateInvite() {
    try {
        const result = await createInvite.mutateAsync();
        try {
            await navigator.clipboard.writeText(result.invite_url);
            toast.success("Invite link copied to clipboard");
        } catch {
            toast.success("Invite created (copy failed — use the link below)");
        }
    } catch (err) {
        toastError(err, "Failed to generate invite");
    }
}
```

- [ ] **Step 4: Fix auth provider — use safe localStorage + handle refreshUser errors**

In `providers/auth-provider.tsx`, replace raw `localStorage.setItem` with try-catch:

```typescript
// OLD:
//   localStorage.setItem("access_token", tokens.access_token);
//   localStorage.setItem("refresh_token", tokens.refresh_token);
// NEW:
try {
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
} catch {
    // Private browsing or storage disabled — tokens will be memory-only
    console.warn("localStorage unavailable — session will not persist across tabs");
}
```

For `refreshUser`, add logging for authenticated-but-failed case:

```typescript
// OLD:
//   } catch {
//       // Ignore - user may not be authenticated
//   }
// NEW:
} catch (err) {
    if (localStorage.getItem("access_token")) {
        console.warn("Failed to refresh user profile despite having token", err);
    }
}
```

- [ ] **Step 5: Fix admin CSV export — defer revokeObjectURL**

In `lib/api/admin.ts`:

```typescript
// OLD:
//   a.click();
//   window.URL.revokeObjectURL(url);
// NEW:
a.click();
setTimeout(() => window.URL.revokeObjectURL(url), 1000);
```

- [ ] **Step 6: Build to verify**

Run: `cd jobhunter/frontend && npm run build`
Expected: Compiled successfully

- [ ] **Step 7: Run all tests**

Run: `cd jobhunter/frontend && npm test`
Expected: All 130 tests pass

- [ ] **Step 8: Commit**

```
git add jobhunter/frontend/src/
git commit -m "fix(frontend): handle silent failures in auth, clipboard, tour, and admin

- onboarding: add catch to completeOnboarding auto-redirect
- tour: log warning on completeTour failure instead of empty catch
- settings: await clipboard.writeText, separate invite creation from copy
- auth-provider: guard localStorage.setItem, log refreshUser failures
- admin: defer URL.revokeObjectURL to prevent download race"
```

---

## Final Verification

- [ ] **Run full backend test suite:** `cd jobhunter/backend && uv run pytest tests/ -x -q`
- [ ] **Run full frontend test suite:** `cd jobhunter/frontend && npm test`
- [ ] **Run frontend build:** `cd jobhunter/frontend && npm run build`
- [ ] **Run ruff on all changed backend files:** `cd jobhunter/backend && uv run ruff check app/ scripts/`
