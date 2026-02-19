from pydantic import BaseModel, Field


class CompanyAddRequest(BaseModel):
    domain: str = Field(max_length=255)


class CompanyRejectRequest(BaseModel):
    reason: str = Field(max_length=500)


class CompanyDiscoverRequest(BaseModel):
    industries: list[str] | None = None
    locations: list[str] | None = None
    company_size: str | None = None
    keywords: str | None = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    domain: str
    industry: str | None = None
    size_range: str | None = None
    location_hq: str | None = None
    description: str | None = None
    tech_stack: list[str] | None = None
    funding_stage: str | None = None
    fit_score: float | None = None
    status: str
    research_status: str

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    companies: list[CompanyResponse]
    total: int


class CompanyDossierResponse(BaseModel):
    id: str
    culture_summary: str | None = None
    culture_score: float | None = None
    red_flags: list[str] | None = None
    interview_format: str | None = None
    interview_questions: list[str] | None = None
    compensation_data: dict | None = None
    key_people: list[dict] | None = None
    why_hire_me: str | None = None
    recent_news: list[dict] | None = None

    model_config = {"from_attributes": True}
