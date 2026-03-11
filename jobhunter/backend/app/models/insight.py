import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AnalyticsInsight(TimestampMixin, Base):
    __tablename__ = "analytics_insights"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "pipeline_health" | "outreach_effectiveness" | "skill_gap" | "market_positioning" | "recommendation"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    # "info" | "warning" | "success" | "action_needed"
    data: Mapped[dict | None] = mapped_column(JSONB)
    # Structured data backing this insight (charts, numbers, etc.)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
