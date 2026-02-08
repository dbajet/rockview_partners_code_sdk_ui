from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="New Session")
    status: Mapped[str] = mapped_column(String(32), default="active")
    model: Mapped[str] = mapped_column(String(120))
    permission_mode: Mapped[str] = mapped_column(String(32))
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    claude_session_id: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    messages: Mapped[list["MessageLog"]] = relationship(
        "MessageLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["SessionLog"]] = relationship(
        "SessionLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )
