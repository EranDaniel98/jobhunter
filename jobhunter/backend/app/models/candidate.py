import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(255))
    target_roles: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    target_industries: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    target_locations: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    preferences: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan_tier: Mapped[str] = mapped_column(String(20), default="free", server_default="free", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    # Relationships
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")
    dna: Mapped["CandidateDNA | None"] = relationship(back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSONB)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, failed
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    version_label: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")


class CandidateDNA(TimestampMixin, Base):
    __tablename__ = "candidate_dna"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    embedding = mapped_column(Vector(1536))
    skills_vector = mapped_column(Vector(1536))
    experience_summary: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    gaps: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    career_stage: Mapped[str | None] = mapped_column(String(50))
    transferable_skills: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    candidate: Mapped["Candidate"] = relationship(back_populates="dna")


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # explicit, transferable, adjacent
    proficiency: Mapped[str | None] = mapped_column(String(50))
    years_experience: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(Vector(1536))

    # Relationships
    candidate: Mapped["Candidate"] = relationship(back_populates="skills")
