from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    category: str = Field(..., pattern="^(bug|feature_request|question|other)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    context: dict | None = None


class IncidentResponse(BaseModel):
    id: str
    category: str
    title: str
    github_issue_url: str | None = None
    github_status: str
    created_at: str
    model_config = {"from_attributes": True}


class IncidentAdminResponse(BaseModel):
    id: str
    candidate_email: str
    category: str
    title: str
    description: str
    github_issue_url: str | None = None
    github_issue_number: int | None = None
    github_status: str
    retry_count: int
    created_at: str
    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    items: list[IncidentAdminResponse]
    total: int
    page: int
    per_page: int
