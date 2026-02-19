from datetime import datetime

from pydantic import BaseModel, Field


class OutreachDraftRequest(BaseModel):
    contact_id: str
    language: str = "en"


class OutreachLinkedInRequest(BaseModel):
    contact_id: str
    language: str = "en"


class OutreachEditRequest(BaseModel):
    subject: str | None = Field(None, max_length=500)
    body: str | None = None


class OutreachMessageResponse(BaseModel):
    id: str
    contact_id: str
    candidate_id: str
    channel: str
    message_type: str
    subject: str | None = None
    body: str
    personalization_data: dict | None = None
    status: str
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    replied_at: datetime | None = None

    model_config = {"from_attributes": True}
