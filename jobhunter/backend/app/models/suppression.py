from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EmailSuppression(TimestampMixin, Base):
    __tablename__ = "email_suppressions"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # unsubscribe, bounce, complaint
    suppressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
