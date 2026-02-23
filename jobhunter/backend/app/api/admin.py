import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_db
from app.models.candidate import Candidate
from app.schemas.admin import (
    InviteChainItem,
    RegistrationTrend,
    SystemOverview,
    ToggleAdminRequest,
    TopUserItem,
    UserDetail,
    UserListResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


@router.get("/overview", response_model=SystemOverview)
async def get_overview(
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_system_overview(db)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, skip=skip, limit=limit, search=search)


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.get_user_detail(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserDetail)
async def toggle_admin(
    user_id: uuid.UUID,
    body: ToggleAdminRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    candidate = await admin_service.toggle_user_admin(db, user_id, body.is_admin)
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    user = await admin_service.get_user_detail(db, user_id)
    return user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    deleted = await admin_service.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/analytics/registrations", response_model=list[RegistrationTrend])
async def get_registrations(
    days: int = Query(30, ge=1, le=365),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_registration_trend(db, days=days)


@router.get("/analytics/invites", response_model=list[InviteChainItem])
async def get_invites(
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_invite_chain(db)


@router.get("/analytics/top-users", response_model=list[TopUserItem])
async def get_top_users(
    metric: str = Query("messages_sent"),
    limit: int = Query(10, ge=1, le=50),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_top_users(db, metric=metric, limit=limit)
