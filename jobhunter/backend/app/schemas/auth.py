import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegistrationPreferences(BaseModel):
    email_notifications: bool = True


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    invite_code: str = Field(min_length=1, max_length=64)
    preferences: RegistrationPreferences | None = None

    @field_validator("full_name")
    @classmethod
    def sanitize_full_name(cls, v: str) -> str:
        v = re.sub(r"<[^>]*>", "", v).strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if not re.match(r"^[\w\s\-'.]+$", v, re.UNICODE):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("invite_code")
    @classmethod
    def sanitize_invite_code(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9\-_]+$", v):
            raise ValueError("Invalid invite code format")
        return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CandidateResponse(BaseModel):
    id: str
    email: str
    full_name: str
    headline: str | None = None
    location: str | None = None
    target_roles: list[str] | None = None
    target_industries: list[str] | None = None
    target_locations: list[str] | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    is_admin: bool = False
    email_verified: bool = True
    preferences: dict | None = None
    plan_tier: str = "free"
    onboarding_completed_at: datetime | None = None
    onboarding_completed: bool = False
    tour_completed_at: datetime | None = None
    tour_completed: bool = False

    model_config = {"from_attributes": True}
