from datetime import datetime

from pydantic import BaseModel


class PendingActionResponse(BaseModel):
    id: str
    candidate_id: str
    action_type: str
    entity_type: str
    entity_id: str
    status: str
    ai_reasoning: str | None
    metadata_: dict | None = None
    reviewed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    # Enriched context (populated from the entity)
    message_subject: str | None = None
    message_body: str | None = None
    contact_name: str | None = None
    company_name: str | None = None
    message_type: str | None = None
    channel: str | None = None


class PendingActionListResponse(BaseModel):
    actions: list[PendingActionResponse]
    total: int


class PendingCountResponse(BaseModel):
    count: int
