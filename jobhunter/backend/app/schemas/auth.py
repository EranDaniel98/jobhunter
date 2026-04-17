import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


_PASSWORD_COMPLEXITY_MSG = (
    "Password must contain at least one uppercase letter, one lowercase letter,"
    " and one digit"
)


def _normalize_email(value: str) -> str:
    """Emails are case-insensitive by convention — store and compare lowercased."""
    return value.strip().lower()


def _validate_password_complexity(value: str) -> str:
    """Reject passwords that don't have mixed case + a digit.

    Min/max length is enforced separately by the Field(min_length=8, max_length=128)
    constraint. This validator only enforces character-class diversity.
    """
    if not re.search(r"[A-Z]", value):
        raise ValueError(_PASSWORD_COMPLEXITY_MSG)
    if not re.search(r"[a-z]", value):
        raise ValueError(_PASSWORD_COMPLEXITY_MSG)
    if not re.search(r"\d", value):
        raise ValueError(_PASSWORD_COMPLEXITY_MSG)
    return value


class RegistrationPreferences(BaseModel):
    email_notifications: bool = True


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    invite_code: str = Field(min_length=1, max_length=64)
    preferences: RegistrationPreferences | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

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

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


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
