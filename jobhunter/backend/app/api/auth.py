import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.schemas.auth import (
    CandidateResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.candidate import CandidateUpdate
from app.services import auth_service
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()


@router.post("/register", response_model=CandidateResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    candidate = await auth_service.register(db, data)
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        is_admin=candidate.is_admin,
        preferences=candidate.preferences,
    )


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, data)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    return await auth_service.refresh_token(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token:
        await auth_service.logout(token)


@router.get("/me", response_model=CandidateResponse)
async def get_me(candidate: Candidate = Depends(get_current_candidate)):
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        preferences=candidate.preferences,
    )


@router.patch("/me", response_model=CandidateResponse)
async def update_me(
    data: CandidateUpdate,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(candidate, key, value)
    await db.commit()
    await db.refresh(candidate)
    logger.info("candidate_updated", candidate_id=str(candidate.id), fields=list(update_data.keys()))
    return CandidateResponse(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        headline=candidate.headline,
        location=candidate.location,
        target_roles=candidate.target_roles,
        target_industries=candidate.target_industries,
        target_locations=candidate.target_locations,
        salary_min=candidate.salary_min,
        salary_max=candidate.salary_max,
        is_admin=candidate.is_admin,
        preferences=candidate.preferences,
    )


@router.post("/me/password", status_code=204)
async def change_password(
    data: ChangePasswordRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, candidate.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    candidate.password_hash = hash_password(data.new_password)
    await db.commit()
    logger.info("password_changed", candidate_id=str(candidate.id))
