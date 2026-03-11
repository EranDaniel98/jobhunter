import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_confidence: Mapped[float | None] = mapped_column(Float)
    title: Mapped[str | None] = mapped_column(String(255))
    role_type: Mapped[str | None] = mapped_column(String(50))  # hiring_manager, recruiter, team_lead
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    twitter_handle: Mapped[str | None] = mapped_column(String(100))
    hunter_data: Mapped[dict | None] = mapped_column(JSONB)
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False)
    outreach_priority: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="contacts")  # noqa: F821
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
