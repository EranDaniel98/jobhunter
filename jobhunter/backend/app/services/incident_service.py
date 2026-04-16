import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.protocols import GitHubClientProtocol, StorageProtocol
from app.models.candidate import Candidate
from app.models.enums import GitHubSyncStatus, IncidentCategory
from app.models.incident import Incident

logger = structlog.get_logger()

CATEGORY_LABELS = {
    IncidentCategory.BUG: "bug",
    IncidentCategory.FEATURE_REQUEST: "enhancement",
    IncidentCategory.QUESTION: "question",
    IncidentCategory.OTHER: "incident",
}


def _build_issue_body(incident: Incident) -> str:
    ctx = incident.context or {}
    attachments_md = "None"
    if incident.attachments:
        attachments_md = "\n".join(f"![{a['filename']}]({a['url']})" for a in incident.attachments)

    console_errors = ctx.get("console_errors") or "None"
    if isinstance(console_errors, list):
        console_errors = "\n".join(console_errors) if console_errors else "None"

    return f"""## Description

{incident.description}

## Attachments

{attachments_md}

## Context

| Field | Value |
|-------|-------|
| User | {ctx.get("email", "N/A")} |
| Plan | {ctx.get("plan_tier", "N/A")} |
| Page | {ctx.get("page_url", "N/A")} |
| Browser | {ctx.get("browser", "N/A")} |
| OS | {ctx.get("os", "N/A")} |
| Submitted | {incident.created_at} |
| Incident ID | {incident.id} |

## Console Errors

```
{console_errors}
```"""


async def create_incident(
    db: AsyncSession,
    candidate: Candidate,
    category: str,
    title: str,
    description: str,
    context: dict | None,
    files: list[tuple[str, bytes, str]],
    storage: StorageProtocol,
    github: GitHubClientProtocol,
) -> Incident:
    incident_id = uuid.uuid4()

    # Upload attachments
    attachments = []
    for filename, data, content_type in files:
        key = f"incidents/{incident_id}/{filename}"
        url = await storage.upload(key, data, content_type)
        attachments.append(
            {
                "filename": filename,
                "url": url,
                "size_bytes": len(data),
                "content_type": content_type,
            }
        )

    incident = Incident(
        id=incident_id,
        candidate_id=candidate.id,
        category=category,
        title=title,
        description=description,
        context=context,
        attachments=attachments or None,
        github_status=GitHubSyncStatus.PENDING,
        retry_count=0,
    )
    db.add(incident)
    await db.flush()

    # Sync to GitHub
    await _sync_to_github(incident, github)

    await db.commit()
    await db.refresh(incident)
    return incident


async def _sync_to_github(incident: Incident, github: GitHubClientProtocol) -> None:
    try:
        label = CATEGORY_LABELS.get(incident.category, "incident")
        body = _build_issue_body(incident)
        result = await github.create_issue(
            title=f"[{incident.category}] {incident.title}",
            body=body,
            labels=[label],
        )
        incident.github_issue_number = result["number"]
        incident.github_issue_url = result["url"]
        incident.github_status = GitHubSyncStatus.SYNCED
    except Exception:
        logger.exception("github_sync_failed", incident_id=str(incident.id))
        incident.github_status = GitHubSyncStatus.FAILED


async def retry_failed_syncs(db: AsyncSession, github: GitHubClientProtocol) -> int:
    result = await db.execute(
        select(Incident).where(
            Incident.github_status == GitHubSyncStatus.FAILED,
            Incident.retry_count < 5,
        )
    )
    incidents = result.scalars().all()
    retried = 0
    for incident in incidents:
        incident.retry_count += 1
        await _sync_to_github(incident, github)
        retried += 1
    await db.commit()
    return retried


async def list_incidents(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    github_status: str | None = None,
    category: str | None = None,
) -> tuple[list, int]:
    query = select(Incident).join(Candidate)
    count_query = select(func.count(Incident.id))

    if github_status:
        query = query.where(Incident.github_status == github_status)
        count_query = count_query.where(Incident.github_status == github_status)
    if category:
        query = query.where(Incident.category == category)
        count_query = count_query.where(Incident.category == category)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.order_by(Incident.created_at.desc()).offset((page - 1) * per_page).limit(per_page))
    return result.scalars().all(), total


async def get_incident_count(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(Incident.id)))).scalar() or 0
    failed = (
        await db.execute(select(func.count(Incident.id)).where(Incident.github_status == GitHubSyncStatus.FAILED))
    ).scalar() or 0
    return {"total": total, "failed": failed}
