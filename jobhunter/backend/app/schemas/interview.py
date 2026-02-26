from pydantic import BaseModel


class InterviewPrepRequest(BaseModel):
    company_id: str
    prep_type: str


class MockInterviewStartRequest(BaseModel):
    company_id: str
    interview_type: str


class MockInterviewReplyRequest(BaseModel):
    session_id: str
    answer: str


class MockInterviewEndRequest(BaseModel):
    session_id: str


class MockMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_number: int
    feedback: dict | None = None

    model_config = {"from_attributes": True}


class InterviewPrepSessionResponse(BaseModel):
    id: str
    company_id: str
    prep_type: str
    content: dict | None = None
    status: str
    error: str | None = None
    messages: list[MockMessageResponse] = []

    model_config = {"from_attributes": True}


class InterviewPrepListResponse(BaseModel):
    sessions: list[InterviewPrepSessionResponse]
    total: int
