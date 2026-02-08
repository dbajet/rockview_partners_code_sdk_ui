from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core import settings
from app.models import Base


class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url, future=True)
        self._session_maker = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def create_tables(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def wait_until_available(
        self,
        attempts: int = 30,
        delay_seconds: float = 1.0,
        attempt_timeout_seconds: float = 5.0,
    ) -> None:
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                await asyncio.wait_for(
                    self._probe_connection(),
                    timeout=attempt_timeout_seconds,
                )
                return
            except Exception as exc:  # pragma: no cover - network startup timing
                last_error = exc
                print(
                    f"[startup] database not ready (attempt {attempt}/{attempts}): {exc}",
                    flush=True,
                )
                if attempt == attempts:
                    break
                await asyncio.sleep(delay_seconds)

        if last_error is not None:
            raise last_error

    async def _probe_connection(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._session_maker() as session:
            yield session


_database_manager = DatabaseManager(settings.database_url)


def get_database_manager() -> DatabaseManager:
    return _database_manager
