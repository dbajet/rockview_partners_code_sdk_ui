from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models import AgentSession


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def list_for_user(self, user_id: UUID) -> list[AgentSession]:
        query_result = await self._db.execute(
            select(AgentSession)
            .where(AgentSession.user_id == user_id)
            .order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
        )
        result = list(query_result.scalars().all())
        return result

    async def get_session(self, session_id: UUID) -> AgentSession | None:
        query_result = await self._db.execute(select(AgentSession).where(AgentSession.id == session_id))
        result = query_result.scalar_one_or_none()
        return result

    async def update_claude_session_id(self, session: AgentSession, claude_session_id: str | None) -> None:
        # SQLAlchemy tracks in-place mutation on mapped entities; update then commit is required.
        session.claude_session_id = claude_session_id
        await self._db.commit()

    async def update_status(self, session: AgentSession, status: str) -> None:
        # SQLAlchemy tracks in-place mutation on mapped entities; update then commit is required.
        session.status = status
        await self._db.commit()

    async def touch_session(self, session: AgentSession) -> None:
        await self._db.execute(
            update(AgentSession).where(AgentSession.id == session.id).values(updated_at=func.now())
        )
        await self._db.commit()
