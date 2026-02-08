from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentSession


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(
        self,
        *,
        user_id: UUID,
        title: str,
        model: str,
        permission_mode: str,
        system_prompt: str | None,
    ) -> AgentSession:
        session = AgentSession(
            user_id=user_id,
            title=title,
            model=model,
            permission_mode=permission_mode,
            system_prompt=system_prompt,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_for_user(self, user_id: UUID) -> Sequence[AgentSession]:
        result = await self.db.execute(
            select(AgentSession)
            .where(AgentSession.user_id == user_id)
            .order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
        )
        return result.scalars().all()

    async def get_session(self, session_id: UUID) -> AgentSession | None:
        result = await self.db.execute(select(AgentSession).where(AgentSession.id == session_id))
        return result.scalar_one_or_none()

    async def update_claude_session_id(self, session: AgentSession, claude_session_id: str) -> None:
        session.claude_session_id = claude_session_id
        await self.db.commit()

    async def update_status(self, session: AgentSession, status: str) -> None:
        session.status = status
        await self.db.commit()

    async def touch_session(self, session: AgentSession) -> None:
        await self.db.execute(
            update(AgentSession).where(AgentSession.id == session.id).values(updated_at=func.now())
        )
        await self.db.commit()
