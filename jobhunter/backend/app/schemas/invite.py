from datetime import datetime

from pydantic import BaseModel


class InviteCreateResponse(BaseModel):
    code: str
    invite_url: str
    expires_at: datetime


class InviteValidateResponse(BaseModel):
    valid: bool
    invited_by_name: str | None = None


class InviteListItem(BaseModel):
    id: str
    code: str
    is_used: bool
    used_by_email: str | None = None
    expires_at: datetime
    created_at: datetime
