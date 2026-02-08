from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_users(self) -> Sequence[User]:
        result = await self.db.execute(select(User).order_by(User.created_at.asc()))
        return result.scalars().all()

    async def get_user(self, user_id: UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create_user(self, username: str, display_name: str) -> User:
        user = User(username=username, display_name=display_name)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
