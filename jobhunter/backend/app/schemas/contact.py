from pydantic import BaseModel, EmailStr, Field


class ContactFindRequest(BaseModel):
    company_id: str
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)


class ContactResponse(BaseModel):
    id: str
    company_id: str
    full_name: str
    email: str | None = None
    email_verified: bool = False
    email_confidence: float | None = None
    title: str | None = None
    role_type: str | None = None
    is_decision_maker: bool = False
    outreach_priority: int = 0

    model_config = {"from_attributes": True}
