from pydantic import BaseModel, field_validator


class JobPostingCreateRequest(BaseModel):
    title: str
    company_name: str | None = None
    company_id: str | None = None
    url: str | None = None
    raw_text: str


class ResumeTipItem(BaseModel):
    section: str
    tip: str
    priority: str


class ApplyAnalysisResponse(BaseModel):
    id: str
    job_posting_id: str
    readiness_score: float
    resume_tips: list[ResumeTipItem]
    cover_letter: str
    ats_keywords: list[str]
    missing_skills: list[str]
    matching_skills: list[str]
    status: str


class JobPostingResponse(BaseModel):
    id: str
    title: str
    company_name: str | None = None
    company_id: str | None = None
    url: str | None = None
    status: str
    ats_keywords: list[str] | None = None
    parsed_requirements: dict | None = None

    @field_validator("id", "company_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v

    model_config = {"from_attributes": True}


class JobPostingListResponse(BaseModel):
    postings: list[JobPostingResponse]
    total: int


class ScrapeUrlRequest(BaseModel):
    url: str


class ScrapeUrlResponse(BaseModel):
    raw_text: str
    title: str | None = None
    company_name: str | None = None
