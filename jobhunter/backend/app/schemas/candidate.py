from pydantic import BaseModel, Field


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    headline: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=255)
    target_roles: list[str] | None = Field(None, max_length=10)
    target_industries: list[str] | None = Field(None, max_length=10)
    target_locations: list[str] | None = Field(None, max_length=10)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    preferences: dict | None = None


class ResumeUploadResponse(BaseModel):
    id: str
    file_path: str
    is_primary: bool
    parsed_data: dict | None = None

    model_config = {"from_attributes": True}


class SkillResponse(BaseModel):
    id: str
    name: str
    category: str
    proficiency: str | None = None
    years_experience: float | None = None
    evidence: str | None = None

    model_config = {"from_attributes": True}


class CandidateDNAResponse(BaseModel):
    id: str
    experience_summary: str | None = None
    strengths: list[str] | None = None
    gaps: list[str] | None = None
    career_stage: str | None = None
    transferable_skills: dict | None = None
    skills: list[SkillResponse] = []

    model_config = {"from_attributes": True}


class ParsedResumeSchema(BaseModel):
    name: str | None = None
    headline: str | None = None
    experiences: list[dict] = []
    skills: list[str] = []
    education: list[dict] = []
    certifications: list[str] = []
    summary: str | None = None
