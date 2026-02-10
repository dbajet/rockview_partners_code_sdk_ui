from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.models import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_users(self) -> list[User]:
        query_result = await self._db.execute(select(User).order_by(User.created_at.asc()))
        result = list(query_result.scalars().all())
        return result

    async def get_user(self, user_id: UUID) -> User | None:
        query_result = await self._db.execute(select(User).where(User.id == user_id))
        result = query_result.scalar_one_or_none()
        return result

    async def get_user_by_username(self, username: str) -> User | None:
        query_result = await self._db.execute(select(User).where(User.username == username))
        result = query_result.scalar_one_or_none()
        return result

    async def create_user(self, username: str, display_name: str) -> User:
        user = User(username=username, display_name=display_name)
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user
