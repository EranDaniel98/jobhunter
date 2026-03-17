import hashlib
import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_openai
from app.infrastructure.storage import get_storage
from app.models.candidate import Resume

logger = structlog.get_logger()

RESUME_PARSE_PROMPT = """You are a resume parser. Extract structured information from the following resume text.
Return a JSON object with these fields:
- name: string
- headline: string (professional title/headline)
- experiences: array of {company, title, dates, description, achievements: string[]}
- skills: string[] (all technical and soft skills mentioned)
- education: array of {institution, degree, year}
- certifications: string[]
- summary: string (1-2 sentence professional summary)

Be thorough and extract ALL information. Do not fabricate or embellish - only extract what is explicitly stated."""

RESUME_PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "headline": {"type": "string"},
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "dates": {"type": "string"},
                    "description": {"type": "string"},
                    "achievements": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "title", "dates", "description", "achievements"],
                "additionalProperties": False,
            },
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "degree": {"type": "string"},
                    "year": {"type": "string"},
                },
                "required": ["institution", "degree", "year"],
                "additionalProperties": False,
            },
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["name", "headline", "experiences", "skills", "education", "certifications", "summary"],
    "additionalProperties": False,
}


SKILLS_EXTRACTION_PROMPT = """
You are a skills extraction specialist. Analyze the following resume text and extract all skills.

For each skill, provide:
- name: the skill name
- category: one of "technical", "domain", "soft", "transferable"
- proficiency: one of "beginner", "intermediate", "advanced", "expert" (estimate from context)
- years_experience: estimated years (integer or null if unknown)
- evidence: a brief quote or reference from the resume supporting this skill

Be thorough. Include programming languages, frameworks, tools, methodologies, soft skills, and domain expertise.
Only extract skills explicitly mentioned or clearly implied by the resume content."""

SKILLS_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": ["technical", "domain", "soft", "transferable"]},
                    "proficiency": {"type": "string", "enum": ["beginner", "intermediate", "advanced", "expert"]},
                    "years_experience": {"type": ["integer", "null"]},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "category", "proficiency", "years_experience", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["skills"],
    "additionalProperties": False,
}

DNA_SUMMARY_PROMPT = """
You are a career analyst. Based on the following parsed resume data, generate a candidate DNA profile.

Provide:
- experience_summary: 2-3 sentence summary of their career trajectory
- strengths: array of 3-5 key professional strengths
- gaps: array of 1-3 potential skill or experience gaps
- career_stage: one of "entry", "mid", "senior", "lead", "executive"

Be honest and constructive. Base everything on the actual resume data provided."""

DNA_SCHEMA = {
    "type": "object",
    "properties": {
        "experience_summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "career_stage": {"type": "string", "enum": ["entry", "mid", "senior", "lead", "executive"]},
    },
    "required": ["experience_summary", "strengths", "gaps", "career_stage"],
    "additionalProperties": False,
}


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def _extract_text_from_docx(file_bytes: bytes) -> str:
    import io

    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs).strip()


async def upload_resume(db: AsyncSession, candidate_id: uuid.UUID, file_bytes: bytes, filename: str) -> Resume:
    # Determine file type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx"):
        raise ValueError("Only PDF and DOCX files are supported")

    # Compute hash and save file via storage abstraction
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    storage_key = f"resumes/{candidate_id}/{file_hash}.{ext}"
    content_type = (
        "application/pdf" if ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    storage = get_storage()
    await storage.upload(storage_key, file_bytes, content_type)

    # Extract text (offload CPU-bound parsing to thread pool)
    import asyncio

    extractor = _extract_text_from_pdf if ext == "pdf" else _extract_text_from_docx
    raw_text = await asyncio.to_thread(extractor, file_bytes)

    # Mark previous resumes as non-primary (atomic single UPDATE)
    await db.execute(
        update(Resume).where(Resume.candidate_id == candidate_id, Resume.is_primary).values(is_primary=False)
    )

    resume = Resume(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        file_path=storage_key,
        file_hash=file_hash,
        raw_text=raw_text,
        is_primary=True,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    logger.info("resume_uploaded", resume_id=str(resume.id), candidate_id=str(candidate_id))
    return resume


async def parse_resume(db: AsyncSession, resume_id: uuid.UUID) -> Resume:
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise ValueError("Resume not found")

    if not resume.raw_text:
        raise ValueError("Resume has no extracted text")

    client = get_openai()
    parsed = await client.parse_structured(RESUME_PARSE_PROMPT, resume.raw_text, RESUME_PARSE_SCHEMA)

    resume.parsed_data = parsed
    await db.commit()
    await db.refresh(resume)
    logger.info("resume_parsed", resume_id=str(resume_id))
    return resume
