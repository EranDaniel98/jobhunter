from datetime import datetime

from pydantic import BaseModel


class SystemOverview(BaseModel):
    total_users: int
    total_companies: int
    total_messages_sent: int
    total_contacts: int
    total_invites_used: int
    active_users_7d: int
    active_users_30d: int


class UserListItem(BaseModel):
    id: str
    email: str
    full_name: str
    is_admin: bool
    created_at: datetime
    companies_count: int = 0
    messages_sent_count: int = 0
    is_active: bool = True


class UserListResponse(BaseModel):
    users: list[UserListItem]
    total: int


class UserDetail(UserListItem):
    invited_by_email: str | None = None
    invite_code_used: str | None = None
    recent_activity: list[dict] = []


class RegistrationTrend(BaseModel):
    date: str
    count: int


class InviteChainItem(BaseModel):
    inviter_email: str
    inviter_name: str
    invitee_email: str | None = None
    invitee_name: str | None = None
    code: str
    used_at: datetime | None = None


class TopUserItem(BaseModel):
    email: str
    full_name: str
    metric_value: int
    metric_name: str


class ToggleAdminRequest(BaseModel):
    is_admin: bool


class ToggleActiveRequest(BaseModel):
    is_active: bool


class ActivityFeedItem(BaseModel):
    id: str
    user_email: str
    user_name: str
    event_type: str
    entity_type: str | None = None
    details: dict | None = None
    occurred_at: datetime


class AuditLogItem(BaseModel):
    id: str
    admin_email: str | None = None
    admin_name: str | None = None
    action: str
    target_email: str | None = None
    target_name: str | None = None
    details: dict | None = None
    created_at: datetime


class BroadcastRequest(BaseModel):
    subject: str
    body: str


class BroadcastResponse(BaseModel):
    sent_count: int
    skipped_count: int
