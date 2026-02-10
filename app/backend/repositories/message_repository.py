from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models import MessageLog


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
        self._db.add(message)
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def list_messages(self, session_id: UUID, limit: int = 500) -> list[MessageLog]:
        query_result = await self._db.execute(
            select(MessageLog)
            .where(MessageLog.session_id == session_id)
            .order_by(MessageLog.created_at.asc())
            .limit(limit)
        )
        result = list(query_result.scalars().all())
        return result
