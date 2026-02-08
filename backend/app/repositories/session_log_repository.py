from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SessionLog


class SessionLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_log(self, *, session_id: UUID, event_type: str, details: dict) -> SessionLog:
        log = SessionLog(session_id=session_id, event_type=event_type, details=details)
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_logs(self, session_id: UUID, limit: int = 500) -> Sequence[SessionLog]:
        result = await self.db.execute(
            select(SessionLog)
            .where(SessionLog.session_id == session_id)
            .order_by(SessionLog.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()
