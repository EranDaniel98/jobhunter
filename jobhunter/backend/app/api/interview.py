import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_candidate, get_db, get_openai
from app.rate_limit import limiter
from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company
from app.models.interview import InterviewPrepSession, MockInterviewMessage
from app.schemas.interview import (
    InterviewPrepListResponse,
    InterviewPrepRequest,
    InterviewPrepSessionResponse,
    MockInterviewEndRequest,
    MockInterviewReplyRequest,
    MockInterviewStartRequest,
    MockMessageResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])

VALID_PREP_TYPES = {"company_qa", "behavioral", "technical", "culture_fit", "salary_negotiation"}
VALID_INTERVIEW_TYPES = {"behavioral", "technical", "mixed"}

MOCK_SYSTEM_PROMPT = (
    "You are a professional interviewer conducting a {interview_type} interview for {company_name} ({industry}). "
    "The candidate's background: {candidate_summary}. "
    "Ask one question at a time. After the candidate answers, provide brief feedback, then ask the next question. "
    "Be realistic but encouraging. Adapt difficulty based on responses."
)

MOCK_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["overall_score", "strengths", "improvements", "summary"],
    "additionalProperties": False,
}


async def _run_interview_prep(candidate_id: str, company_id: str, prep_type: str):
    """Background task to run the interview prep pipeline."""
    from app.graphs.interview_prep import get_interview_prep_pipeline

    thread_id = f"interview-prep-{uuid.uuid4()}"
    state = {
        "candidate_id": candidate_id,
        "company_id": company_id,
        "prep_type": prep_type,
        "session_id": None,
        "context": None,
        "content": None,
        "status": "pending",
        "error": None,
    }

    try:
        graph = get_interview_prep_pipeline()
        await graph.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    except Exception as e:
        logger.error("interview_prep_bg_failed", error=str(e))


@router.post("/generate", response_model=InterviewPrepSessionResponse)
@limiter.limit("20/day")
async def generate_prep(
    request: Request,
    req: InterviewPrepRequest,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Generate interview prep material for a company."""
    if req.prep_type not in VALID_PREP_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid prep_type. Must be one of: {sorted(VALID_PREP_TYPES)}")

    # Verify company belongs to candidate
    result = await db.execute(
        select(Company).where(Company.id == uuid.UUID(req.company_id), Company.candidate_id == candidate.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Company not found")

    background_tasks.add_task(_run_interview_prep, str(candidate.id), req.company_id, req.prep_type)

    return InterviewPrepSessionResponse(
        id="pending", company_id=req.company_id, prep_type=req.prep_type, status="pending"
    )


@router.get("/sessions", response_model=InterviewPrepListResponse)
async def list_sessions(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
    company_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List interview prep sessions for the authenticated candidate."""
    query = (
        select(InterviewPrepSession)
        .where(InterviewPrepSession.candidate_id == candidate.id)
        .options(selectinload(InterviewPrepSession.messages))
        .order_by(InterviewPrepSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if company_id:
        query = query.where(InterviewPrepSession.company_id == uuid.UUID(company_id))

    result = await db.execute(query)
    sessions = result.scalars().unique().all()

    count_query = select(func.count(InterviewPrepSession.id)).where(
        InterviewPrepSession.candidate_id == candidate.id
    )
    if company_id:
        count_query = count_query.where(InterviewPrepSession.company_id == uuid.UUID(company_id))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return InterviewPrepListResponse(
        sessions=[InterviewPrepSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get("/sessions/{session_id}", response_model=InterviewPrepSessionResponse)
async def get_session(
    session_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific interview prep session with messages."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(session_id),
            InterviewPrepSession.candidate_id == candidate.id,
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return InterviewPrepSessionResponse.model_validate(session)


@router.post("/mock/start", response_model=InterviewPrepSessionResponse)
@limiter.limit("10/day")
async def start_mock_interview(
    request: Request,
    req: MockInterviewStartRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Start a mock interview session."""
    if req.interview_type not in VALID_INTERVIEW_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid interview_type. Must be one of: {sorted(VALID_INTERVIEW_TYPES)}")

    # Verify company
    result = await db.execute(
        select(Company).where(Company.id == uuid.UUID(req.company_id), Company.candidate_id == candidate.id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Load DNA
    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id))
    dna = dna_result.scalar_one_or_none()

    # Create session
    session = InterviewPrepSession(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        company_id=company.id,
        prep_type="mock_interview",
        content={"interview_type": req.interview_type, "status": "in_progress", "score": None},
        status="in_progress",
    )
    db.add(session)

    # Generate first interviewer question
    system_prompt = MOCK_SYSTEM_PROMPT.format(
        interview_type=req.interview_type,
        company_name=company.name,
        industry=company.industry or "Technology",
        candidate_summary=dna.experience_summary if dna else "Software engineer",
    )

    client = get_openai()
    first_question = await client.chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin the interview. Ask your first question."},
    ])

    msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content=first_question,
        turn_number=1,
    )
    db.add(msg)
    await db.commit()

    # Reload with messages
    result = await db.execute(
        select(InterviewPrepSession)
        .where(InterviewPrepSession.id == session.id)
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one()

    return InterviewPrepSessionResponse.model_validate(session)


@router.post("/mock/reply", response_model=MockMessageResponse)
async def reply_mock_interview(
    req: MockInterviewReplyRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Reply to a mock interview question. Returns interviewer's next response."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(req.session_id),
            InterviewPrepSession.candidate_id == candidate.id,
            InterviewPrepSession.prep_type == "mock_interview",
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Mock interview session not found")

    content_data = session.content or {}
    if content_data.get("status") == "completed":
        raise HTTPException(status_code=400, detail="This mock interview is already completed")

    # Save candidate's answer
    max_turn = max((m.turn_number for m in session.messages), default=0)
    candidate_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="candidate",
        content=req.answer,
        turn_number=max_turn + 1,
    )
    db.add(candidate_msg)

    # Build chat history
    dna_result = await db.execute(select(CandidateDNA).where(CandidateDNA.candidate_id == candidate.id))
    dna = dna_result.scalar_one_or_none()

    company_result = await db.execute(select(Company).where(Company.id == session.company_id))
    company = company_result.scalar_one()

    system_prompt = MOCK_SYSTEM_PROMPT.format(
        interview_type=content_data.get("interview_type", "mixed"),
        company_name=company.name,
        industry=company.industry or "Technology",
        candidate_summary=dna.experience_summary if dna else "Software engineer",
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in session.messages:
        role = "assistant" if m.role == "interviewer" else "user"
        messages.append({"role": role, "content": m.content})
    messages.append({"role": "user", "content": req.answer})

    client = get_openai()
    response = await client.chat(messages)

    interviewer_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="interviewer",
        content=response,
        turn_number=max_turn + 2,
    )
    db.add(interviewer_msg)
    await db.commit()

    return MockMessageResponse.model_validate(interviewer_msg)


@router.post("/mock/end", response_model=InterviewPrepSessionResponse)
async def end_mock_interview(
    req: MockInterviewEndRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """End a mock interview and get final feedback."""
    result = await db.execute(
        select(InterviewPrepSession)
        .where(
            InterviewPrepSession.id == uuid.UUID(req.session_id),
            InterviewPrepSession.candidate_id == candidate.id,
            InterviewPrepSession.prep_type == "mock_interview",
        )
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Mock interview session not found")

    # Build transcript
    transcript = "\n".join(
        f"{'Interviewer' if m.role == 'interviewer' else 'Candidate'}: {m.content}"
        for m in session.messages
    )

    prompt = (
        "You are an interview coach. Review this mock interview transcript and provide final feedback.\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Provide a JSON response with: overall_score (0-10), strengths (list), improvements (list), summary (string)."
    )
    client = get_openai()
    feedback = await client.parse_structured(prompt, "", MOCK_FEEDBACK_SCHEMA)

    # Save feedback as final message
    max_turn = max((m.turn_number for m in session.messages), default=0)
    feedback_msg = MockInterviewMessage(
        id=uuid.uuid4(),
        session_id=session.id,
        role="feedback",
        content=feedback.get("summary", "Interview complete."),
        turn_number=max_turn + 1,
        feedback=feedback,
    )
    db.add(feedback_msg)

    # Update session content
    content_data = session.content or {}
    content_data["status"] = "completed"
    content_data["score"] = feedback.get("overall_score")
    session.content = content_data
    session.status = "completed"
    await db.commit()

    # Reload with updated messages
    result = await db.execute(
        select(InterviewPrepSession)
        .where(InterviewPrepSession.id == session.id)
        .options(selectinload(InterviewPrepSession.messages))
    )
    session = result.scalar_one()

    return InterviewPrepSessionResponse.model_validate(session)
