import hashlib
import json
import os
import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_openai
from app.models.candidate import Candidate, CandidateDNA, Resume, Skill
from app.services.embedding_service import batch_embed, embed_text

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

Be thorough and extract ALL information. Do not fabricate or embellish — only extract what is explicitly stated."""

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

SKILLS_EXTRACTION_PROMPT = """Analyze this resume and categorize the candidate's skills into three categories:

1. **explicit**: Skills directly stated in the resume
2. **transferable**: Skills implied by their experience (e.g., "led a team of 5" implies leadership, project management)
3. **adjacent**: Skills the candidate could credibly claim based on their experience (e.g., a Python backend engineer could credibly claim API design)

For each skill, provide:
- name: the skill name
- category: explicit/transferable/adjacent
- proficiency: beginner/intermediate/advanced/expert
- years_experience: estimated years (float)
- evidence: brief quote or reference from resume supporting this skill

Return JSON with a "skills" array."""

SKILLS_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": ["explicit", "transferable", "adjacent"]},
                    "proficiency": {"type": "string", "enum": ["beginner", "intermediate", "advanced", "expert"]},
                    "years_experience": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "category", "proficiency", "years_experience", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["skills"],
    "additionalProperties": False,
}

DNA_SUMMARY_PROMPT = """Based on this parsed resume, generate a comprehensive candidate DNA profile:

1. experience_summary: 2-3 sentence narrative of their career arc
2. strengths: top 5 professional strengths (string array)
3. gaps: 2-3 potential gaps or areas for growth (string array)
4. career_stage: one of early/mid/senior/staff/principal/executive

Return JSON."""

DNA_SCHEMA = {
    "type": "object",
    "properties": {
        "experience_summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "career_stage": {"type": "string", "enum": ["early", "mid", "senior", "staff", "principal", "executive"]},
    },
    "required": ["experience_summary", "strengths", "gaps", "career_stage"],
    "additionalProperties": False,
}


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def _extract_text_from_docx(file_bytes: bytes) -> str:
    from docx import Document
    import io
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs).strip()


async def upload_resume(
    db: AsyncSession, candidate_id: uuid.UUID, file_bytes: bytes, filename: str
) -> Resume:
    # Determine file type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx"):
        raise ValueError("Only PDF and DOCX files are supported")

    # Compute hash and save file
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(candidate_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}.{ext}")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Extract text
    if ext == "pdf":
        raw_text = _extract_text_from_pdf(file_bytes)
    else:
        raw_text = _extract_text_from_docx(file_bytes)

    # Mark previous resumes as non-primary (atomic single UPDATE)
    await db.execute(
        update(Resume)
        .where(Resume.candidate_id == candidate_id, Resume.is_primary == True)
        .values(is_primary=False)
    )

    resume = Resume(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        file_path=file_path,
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
    parsed = await client.parse_structured(
        RESUME_PARSE_PROMPT, resume.raw_text, RESUME_PARSE_SCHEMA
    )

    resume.parsed_data = parsed
    await db.commit()
    await db.refresh(resume)
    logger.info("resume_parsed", resume_id=str(resume_id))
    return resume


async def generate_candidate_dna(db: AsyncSession, candidate_id: uuid.UUID) -> CandidateDNA:
    # Get primary resume
    result = await db.execute(
        select(Resume).where(
            Resume.candidate_id == candidate_id, Resume.is_primary == True
        )
    )
    resume = result.scalar_one_or_none()
    if not resume or not resume.parsed_data:
        raise ValueError("No parsed resume found")

    client = get_openai()
    resume_text = resume.raw_text or json.dumps(resume.parsed_data)

    # Generate embeddings
    embedding = await embed_text(resume_text)

    # Generate skills taxonomy
    skills_data = await client.parse_structured(
        SKILLS_EXTRACTION_PROMPT, resume_text, SKILLS_SCHEMA
    )

    # Generate DNA summary
    dna_data = await client.parse_structured(
        DNA_SUMMARY_PROMPT, json.dumps(resume.parsed_data), DNA_SCHEMA
    )

    # Generate skills vector (embed all skill names together)
    skill_names = [s["name"] for s in skills_data.get("skills", [])]
    skills_vector = await embed_text(" ".join(skill_names)) if skill_names else embedding

    # Delete existing DNA and skills
    existing = await db.execute(
        select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id)
    )
    old_dna = existing.scalar_one_or_none()
    if old_dna:
        await db.delete(old_dna)

    existing_skills = await db.execute(
        select(Skill).where(Skill.candidate_id == candidate_id)
    )
    for s in existing_skills.scalars():
        await db.delete(s)

    # Create DNA
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        embedding=embedding,
        skills_vector=skills_vector,
        experience_summary=dna_data.get("experience_summary"),
        strengths=dna_data.get("strengths"),
        gaps=dna_data.get("gaps"),
        career_stage=dna_data.get("career_stage"),
        transferable_skills={
            s["name"]: s.get("evidence", "")
            for s in skills_data.get("skills", [])
            if s.get("category") == "transferable"
        },
    )
    db.add(dna)

    # Create skill records with embeddings (batched single API call)
    skills_list = skills_data.get("skills", [])
    skill_names = [s["name"] for s in skills_list]
    skill_embeddings = await batch_embed(skill_names) if skill_names else []

    for skill_data, skill_embedding in zip(skills_list, skill_embeddings):
        skill = Skill(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            name=skill_data["name"],
            category=skill_data.get("category", "explicit"),
            proficiency=skill_data.get("proficiency"),
            years_experience=skill_data.get("years_experience"),
            evidence=skill_data.get("evidence"),
            embedding=skill_embedding,
        )
        db.add(skill)

    await db.commit()
    await db.refresh(dna)
    logger.info("candidate_dna_generated", candidate_id=str(candidate_id))
    return dna
