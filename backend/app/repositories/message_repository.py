from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageLog


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_message(
        self,
        *,
        session_id: UUID,
        role: str,
        message_type: str,
        payload: dict,
        raw_text: str | None,
    ) -> MessageLog:
        message = MessageLog(
            session_id=session_id,
            role=role,
            message_type=message_type,
            payload=payload,
            raw_text=raw_text,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def list_messages(self, session_id: UUID, limit: int = 500) -> Sequence[MessageLog]:
        result = await self.db.execute(
            select(MessageLog)
            .where(MessageLog.session_id == session_id)
            .order_by(MessageLog.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()
