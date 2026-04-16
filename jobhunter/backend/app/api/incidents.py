import json

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_current_candidate, get_db, get_github
from app.infrastructure.protocols import GitHubClientProtocol, StorageProtocol
from app.infrastructure.storage import get_storage
from app.models.candidate import Candidate
from app.rate_limit import limiter
from app.schemas.incident import IncidentAdminResponse, IncidentListResponse, IncidentResponse
from app.services import incident_service

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = structlog.get_logger()

MAX_FILES = 3
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("", response_model=IncidentResponse, status_code=201)
@limiter.limit("3/hour")
async def submit_incident(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    context: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
    github: GitHubClientProtocol = Depends(get_github),
):
    if category not in ("bug", "feature_request", "question", "other"):
        raise HTTPException(status_code=400, detail="Invalid category")
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="Title too long (max 200)")
    if len(description) > 5000:
        raise HTTPException(status_code=400, detail="Description too long (max 5000)")

    try:
        context_data = json.loads(context)
    except json.JSONDecodeError:
        context_data = {}

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_FILES} files allowed")

    file_tuples: list[tuple[str, bytes, str]] = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File {f.filename} is not an image")
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {f.filename} too large (max 5MB)")
        file_tuples.append((f.filename or "image", data, f.content_type))

    storage: StorageProtocol = get_storage()
    incident = await incident_service.create_incident(
        db=db,
        candidate=candidate,
        category=category,
        title=title,
        description=description,
        context=context_data,
        files=file_tuples,
        storage=storage,
        github=github,
    )

    return IncidentResponse(
        id=str(incident.id),
        category=incident.category,
        title=incident.title,
        github_issue_url=incident.github_issue_url,
        github_status=incident.github_status,
        created_at=str(incident.created_at),
    )


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    github_status: str | None = Query(None),
    category: str | None = Query(None),
    candidate: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await incident_service.list_incidents(
        db=db,
        page=page,
        per_page=per_page,
        github_status=github_status,
        category=category,
    )
    return IncidentListResponse(
        items=[
            IncidentAdminResponse(
                id=str(i.id),
                candidate_email=i.candidate.email,
                category=i.category,
                title=i.title,
                description=i.description,
                github_issue_url=i.github_issue_url,
                github_issue_number=i.github_issue_number,
                github_status=i.github_status,
                retry_count=i.retry_count,
                created_at=str(i.created_at),
            )
            for i in items
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats")
async def incident_stats(
    candidate: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await incident_service.get_incident_count(db)
