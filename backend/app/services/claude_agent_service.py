from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import Constants, settings
from app.models import AgentSession, MessageLog, SessionLog, User
from app.repositories import MessageRepository, SessionLogRepository, SessionRepository, UserRepository
from app.runtime import ClaudeMessageSerializer, ClaudeRuntimeRegistry, default_permission_mode
from app.schemas import SessionCreate, UserCreate


class ClaudeAgentService:
    def __init__(self, runtime_registry: ClaudeRuntimeRegistry) -> None:
        self.runtime_registry = runtime_registry

    async def ensure_default_users(self, db: AsyncSession) -> None:
        user_repo = UserRepository(db)
        existing_users = await user_repo.list_users()
        if existing_users:
            return

        for item in settings.default_users_csv.split(","):
            if ":" not in item:
                continue
            username, display_name = [part.strip() for part in item.split(":", 1)]
            if not username or not display_name:
                continue
            await user_repo.create_user(username=username, display_name=display_name)

    async def list_users(self, db: AsyncSession) -> list[User]:
        user_repo = UserRepository(db)
        return list(await user_repo.list_users())

    async def create_user(self, db: AsyncSession, payload: UserCreate) -> User:
        user_repo = UserRepository(db)
        existing = await user_repo.get_user_by_username(payload.username)
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        return await user_repo.create_user(username=payload.username, display_name=payload.display_name)

    async def create_session(self, db: AsyncSession, payload: SessionCreate) -> AgentSession:
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)
        log_repo = SessionLogRepository(db)

        user = await user_repo.get_user(payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        title = payload.title or "New Session"
        model = payload.model or settings.claude_model
        permission_mode = payload.permission_mode or default_permission_mode()

        session = await session_repo.create_session(
            user_id=payload.user_id,
            title=title,
            model=model,
            permission_mode=permission_mode,
            system_prompt=payload.system_prompt if payload.system_prompt is not None else settings.claude_system_prompt,
        )

        await log_repo.create_log(
            session_id=session.id,
            event_type=Constants.SESSION_EVENT_CREATED,
            details={
                "title": session.title,
                "model": session.model,
                "permission_mode": session.permission_mode,
            },
        )
        return session

    async def list_sessions(self, db: AsyncSession, user_id: UUID) -> list[AgentSession]:
        user_repo = UserRepository(db)
        user = await user_repo.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_repo = SessionRepository(db)
        return list(await session_repo.list_for_user(user_id))

    async def get_session(self, db: AsyncSession, session_id: UUID) -> AgentSession:
        session_repo = SessionRepository(db)
        session = await session_repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    async def list_messages(self, db: AsyncSession, session_id: UUID) -> list[MessageLog]:
        await self.get_session(db, session_id)
        message_repo = MessageRepository(db)
        return list(await message_repo.list_messages(session_id))

    async def list_logs(self, db: AsyncSession, session_id: UUID) -> list[SessionLog]:
        await self.get_session(db, session_id)
        log_repo = SessionLogRepository(db)
        return list(await log_repo.list_logs(session_id))

    async def interrupt_session(self, db: AsyncSession, session_id: UUID) -> None:
        session = await self.get_session(db, session_id)
        log_repo = SessionLogRepository(db)
        await self.runtime_registry.interrupt(str(session.id))
        await log_repo.create_log(
            session_id=session.id,
            event_type=Constants.SESSION_EVENT_INTERRUPTED,
            details={"source": Constants.SESSION_SOURCE_UI},
        )

    async def stream_prompt(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        prompt: str,
    ) -> AsyncGenerator[dict, None]:
        session_repo = SessionRepository(db)
        message_repo = MessageRepository(db)
        log_repo = SessionLogRepository(db)

        session = await self.get_session(db, session_id)
        await session_repo.touch_session(session)

        user_message = await message_repo.create_message(
            session_id=session.id,
            role=Constants.ROLE_USER,
            message_type=Constants.MESSAGE_TYPE_PROMPT,
            payload={"prompt": prompt},
            raw_text=prompt,
        )

        await log_repo.create_log(
            session_id=session.id,
            event_type=Constants.SESSION_EVENT_PROMPT_SUBMITTED,
            details={"length": len(prompt)},
        )

        yield {
            "event": Constants.STREAM_EVENT_MESSAGE,
            "payload": {
                "id": str(user_message.id),
                "session_id": str(user_message.session_id),
                "role": user_message.role,
                "message_type": user_message.message_type,
                "payload": user_message.payload,
                "raw_text": user_message.raw_text,
                "created_at": user_message.created_at.isoformat(),
            },
        }

        runtime = await self.runtime_registry.get_or_create(
            local_session_id=str(session.id),
            model=session.model,
            permission_mode=session.permission_mode,
            max_turns=settings.claude_max_turns,
            system_prompt=session.system_prompt,
            resume=session.claude_session_id,
        )

        try:
            async for sdk_message in runtime.query_stream(prompt):
                serialized = ClaudeMessageSerializer.serialize(sdk_message)
                raw_text = ClaudeMessageSerializer.extract_text(serialized)

                saved = await message_repo.create_message(
                    session_id=session.id,
                    role=serialized.get("role", Constants.ROLE_UNKNOWN),
                    message_type=serialized.get("type", Constants.MESSAGE_TYPE_UNKNOWN),
                    payload=serialized,
                    raw_text=raw_text,
                )

                result_session_id = serialized.get("session_id")
                if result_session_id and result_session_id != session.claude_session_id:
                    await session_repo.update_claude_session_id(session, result_session_id)
                    runtime.set_resume(result_session_id)

                if serialized.get("type") == Constants.MESSAGE_TYPE_RESULT:
                    await log_repo.create_log(
                        session_id=session.id,
                        event_type=Constants.SESSION_EVENT_TURN_RESULT,
                        details={
                            "session_id": serialized.get("session_id"),
                            "is_error": serialized.get("is_error", False),
                            "duration_ms": serialized.get("duration_ms"),
                            "cost_usd": serialized.get("total_cost_usd"),
                            "num_turns": serialized.get("num_turns"),
                        },
                    )

                yield {
                    "event": Constants.STREAM_EVENT_MESSAGE,
                    "payload": {
                        "id": str(saved.id),
                        "session_id": str(saved.session_id),
                        "role": saved.role,
                        "message_type": saved.message_type,
                        "payload": saved.payload,
                        "raw_text": saved.raw_text,
                        "created_at": saved.created_at.isoformat(),
                    },
                }

                if self._contains_ask_user_question(serialized):
                    await log_repo.create_log(
                        session_id=session.id,
                        event_type=Constants.SESSION_EVENT_WAITING_USER_ANSWER,
                        details={"message_id": str(saved.id)},
                    )
                    await runtime.interrupt()
                    break
        except Exception as exc:
            await session_repo.update_status(session, Constants.SESSION_STATUS_ERROR)
            error_details = self._build_error_details(exc)
            error_log = await log_repo.create_log(
                session_id=session.id,
                event_type=Constants.SESSION_EVENT_SDK_ERROR,
                details=error_details,
            )
            yield {
                "event": Constants.STREAM_EVENT_ERROR,
                "payload": {
                    "message": error_details["message"],
                    "log_id": str(error_log.id),
                    "created_at": error_log.created_at.isoformat(),
                },
            }

    @staticmethod
    def _build_error_details(exc: Exception) -> dict[str, Any]:
        details: dict[str, Any] = {
            "message": str(exc),
            "exception_type": type(exc).__name__,
        }

        exit_code = getattr(exc, "exit_code", None)
        if exit_code is not None:
            details["exit_code"] = exit_code

        stderr_output = getattr(exc, "stderr", None)
        if stderr_output:
            details["stderr"] = stderr_output

        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            details["cause_type"] = type(cause).__name__
            details["cause_message"] = str(cause)

        return details

    @staticmethod
    def _contains_ask_user_question(serialized_message: dict[str, Any]) -> bool:
        if serialized_message.get("type") != Constants.MESSAGE_TYPE_ASSISTANT:
            return False

        content = serialized_message.get("content")
        if not isinstance(content, list):
            return False

        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("name") == Constants.TOOL_ASK_USER_QUESTION:
                return True
        return False
