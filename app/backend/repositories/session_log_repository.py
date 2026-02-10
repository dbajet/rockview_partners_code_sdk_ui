from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models import SessionLog


class SessionLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_log(self, *, session_id: UUID, event_type: str, details: dict) -> SessionLog:
        log = SessionLog(session_id=session_id, event_type=event_type, details=details)
        self._db.add(log)
        await self._db.commit()
        await self._db.refresh(log)
        return log

    async def list_logs(self, session_id: UUID, limit: int = 500) -> list[SessionLog]:
        query_result = await self._db.execute(
            select(SessionLog)
            .where(SessionLog.session_id == session_id)
            .order_by(SessionLog.created_at.asc())
            .limit(limit)
        )
        result = list(query_result.scalars().all())
        return result
