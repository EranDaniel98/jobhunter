from pydantic import BaseModel


class CompanyNoteResponse(BaseModel):
    id: str
    company_id: str
    content: str

    model_config = {"from_attributes": True}


class CompanyNoteUpsertRequest(BaseModel):
    content: str
