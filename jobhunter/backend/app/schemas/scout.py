from datetime import datetime

from pydantic import BaseModel


class ScoutRunResponse(BaseModel):
    status: str
    thread_id: str


class CompanySignalResponse(BaseModel):
    id: str
    company_id: str
    company_name: str | None = None
    signal_type: str
    title: str
    description: str | None = None
    source_url: str | None = None
    signal_strength: float | None = None
    detected_at: datetime | None = None
    funding_round: str | None = None
    amount: str | None = None

    model_config = {"from_attributes": True}


class ScoutSignalListResponse(BaseModel):
    signals: list[CompanySignalResponse]
    total: int
