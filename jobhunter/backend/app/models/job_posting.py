import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobPosting(TimestampMixin, Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint(
            "application_stage IN ('saved','applied','phone_screen','interview','offer','rejected')",
            name="ck_job_posting_application_stage",
        ),
        {"extend_existing": True},
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(1000))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_requirements: Mapped[dict | None] = mapped_column(JSONB)
    ats_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    application_stage: Mapped[str] = mapped_column(String(30), default="saved", server_default="saved")
