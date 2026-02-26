import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InterviewPrepSession(TimestampMixin, Base):
    __tablename__ = "interview_prep_sessions"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prep_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list["MockInterviewMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="MockInterviewMessage.turn_number"
    )


class MockInterviewMessage(TimestampMixin, Base):
    __tablename__ = "mock_interview_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_prep_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback: Mapped[dict | None] = mapped_column(JSONB)

    session: Mapped["InterviewPrepSession"] = relationship(back_populates="messages")
