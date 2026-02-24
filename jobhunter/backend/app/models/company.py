import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("candidate_id", "domain", name="uq_company_candidate_domain"),)

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    size_range: Mapped[str | None] = mapped_column(String(50))
    location_hq: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    funding_stage: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    hunter_data: Mapped[dict | None] = mapped_column(JSONB)
    fit_score: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(1536))
    status: Mapped[str] = mapped_column(String(20), default="suggested", index=True)  # suggested, approved, rejected
    research_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed, failed
    last_enriched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    dossier: Mapped["CompanyDossier | None"] = relationship(back_populates="company", uselist=False, cascade="all, delete-orphan")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan")  # noqa: F821


class CompanyDossier(TimestampMixin, Base):
    __tablename__ = "company_dossiers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    culture_summary: Mapped[str | None] = mapped_column(Text)
    culture_score: Mapped[float | None] = mapped_column(Float)
    red_flags: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    interview_format: Mapped[str | None] = mapped_column(Text)
    interview_questions: Mapped[dict | None] = mapped_column(JSONB)
    compensation_data: Mapped[dict | None] = mapped_column(JSONB)
    key_people: Mapped[dict | None] = mapped_column(JSONB)
    why_hire_me: Mapped[str | None] = mapped_column(Text)
    recent_news: Mapped[dict | None] = mapped_column(JSONB)
    resume_bullets: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="dossier")
