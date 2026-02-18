import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OutreachMessage(TimestampMixin, Base):
    __tablename__ = "outreach_messages"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="email")  # email, linkedin
    message_type: Mapped[str] = mapped_column(String(20), default="initial")  # initial, followup_1, followup_2, breakup
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization_data: Mapped[dict | None] = mapped_column(JSONB)
    external_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # status: draft, approved, sent, delivered, opened, replied, bounced, failed
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    contact: Mapped["Contact"] = relationship(back_populates="outreach_messages")  # noqa: F821
    events: Mapped[list["MessageEvent"]] = relationship(back_populates="outreach_message", cascade="all, delete-orphan")


class MessageEvent(TimestampMixin, Base):
    __tablename__ = "message_events"

    outreach_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # delivered, opened, clicked, bounced, complained
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    outreach_message: Mapped["OutreachMessage"] = relationship(back_populates="events")
