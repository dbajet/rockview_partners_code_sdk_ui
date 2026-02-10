from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.backend.core.settings import Settings
from app.backend.database import DatabaseManager
from app.backend.claude_sdk import ClaudeConfigFileManager, ClaudeRuntimeRegistry, DefaultPermissionModeResolver
from app.backend.schemas import (
    MessageRead,
    PromptRequest,
    SessionCreate,
    SessionLogRead,
    SessionRead,
    UserCreate,
    UserRead,
)
from app.backend.services import ClaudeAgentService


class ApiApplication:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_manager = DatabaseManager(settings.database_url)
        self._runtime_registry = ClaudeRuntimeRegistry(settings)
        self._permission_mode_resolver = DefaultPermissionModeResolver(settings)
        self._service = ClaudeAgentService(
            runtime_registry=self._runtime_registry,
            settings=settings,
            permission_mode_resolver=self._permission_mode_resolver,
        )

        self._static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"

        self.app = FastAPI(title=self._settings.app_name, lifespan=self._lifespan)
        self._configure_middleware()
        self._configure_static()
        self._configure_routes()

    @asynccontextmanager
    async def _lifespan(self, _: FastAPI) -> AsyncGenerator[None, None]:
        ClaudeConfigFileManager.ensure_files()

        await self._db_manager.wait_until_available()
        await self._db_manager.create_tables()

        async with self._db_manager.session() as db:
            await self._service.ensure_default_users(db)

        yield

        await self._runtime_registry.close_all()

    def _configure_middleware(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _configure_static(self) -> None:
        self.app.mount(
            "/static",
            StaticFiles(directory=self._static_dir.as_posix()),
            name="static",
        )

    def _configure_routes(self) -> None:
        self.app.add_api_route("/", self.index, methods=["GET"], include_in_schema=False)
        self.app.add_api_route("/api/health", self.health, methods=["GET"])
        self.app.add_api_route(
            "/api/users",
            self.list_users,
            methods=["GET"],
            response_model=list[UserRead],
        )
        self.app.add_api_route(
            "/api/users",
            self.create_user,
            methods=["POST"],
            response_model=UserRead,
            status_code=201,
        )
        self.app.add_api_route(
            "/api/users/{user_id}/sessions",
            self.list_sessions,
            methods=["GET"],
            response_model=list[SessionRead],
        )
        self.app.add_api_route(
            "/api/sessions",
            self.create_session,
            methods=["POST"],
            response_model=SessionRead,
            status_code=201,
        )
        self.app.add_api_route(
            "/api/sessions/{session_id}",
            self.get_session,
            methods=["GET"],
            response_model=SessionRead,
        )
        self.app.add_api_route(
            "/api/sessions/{session_id}/messages",
            self.list_messages,
            methods=["GET"],
            response_model=list[MessageRead],
        )
        self.app.add_api_route(
            "/api/sessions/{session_id}/logs",
            self.list_logs,
            methods=["GET"],
            response_model=list[SessionLogRead],
        )
        self.app.add_api_route(
            "/api/sessions/{session_id}/interrupt",
            self.interrupt_session,
            methods=["POST"],
            status_code=204,
        )
        self.app.add_api_route(
            "/api/sessions/{session_id}/messages/stream",
            self.stream_messages,
            methods=["POST"],
        )

    async def index(self) -> FileResponse:
        result = FileResponse(self._static_dir / "index.html")
        return result

    async def health(self) -> dict[str, str]:
        result = {"status": "ok"}
        return result

    async def list_users(self) -> list[UserRead]:
        async with self._db_manager.session() as db:
            users = await self._service.list_users(db)
        result = [UserRead.model_validate(user) for user in users]
        return result

    async def create_user(self, payload: UserCreate) -> UserRead:
        async with self._db_manager.session() as db:
            user = await self._service.create_user(db, payload)
        result = UserRead.model_validate(user)
        return result

    async def list_sessions(self, user_id: UUID) -> list[SessionRead]:
        async with self._db_manager.session() as db:
            sessions = await self._service.list_sessions(db, user_id)
        result = [SessionRead.model_validate(session) for session in sessions]
        return result

    async def create_session(self, payload: SessionCreate) -> SessionRead:
        async with self._db_manager.session() as db:
            session = await self._service.create_session(db, payload)
        result = SessionRead.model_validate(session)
        return result

    async def get_session(self, session_id: UUID) -> SessionRead:
        async with self._db_manager.session() as db:
            session = await self._service.get_session(db, session_id)
        result = SessionRead.model_validate(session)
        return result

    async def list_messages(self, session_id: UUID) -> list[MessageRead]:
        async with self._db_manager.session() as db:
            messages = await self._service.list_messages(db, session_id)
        result = [MessageRead.model_validate(message) for message in messages]
        return result

    async def list_logs(self, session_id: UUID) -> list[SessionLogRead]:
        async with self._db_manager.session() as db:
            logs = await self._service.list_logs(db, session_id)
        result = [SessionLogRead.model_validate(log) for log in logs]
        return result

    async def interrupt_session(self, session_id: UUID) -> None:
        async with self._db_manager.session() as db:
            await self._service.interrupt_session(db, session_id)

    async def stream_messages(self, session_id: UUID, payload: PromptRequest) -> StreamingResponse:
        prompt = payload.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt must not be empty")

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        result = StreamingResponse(
            self._event_stream(session_id=session_id, prompt=prompt),
            media_type="text/event-stream",
            headers=headers,
        )
        return result

    async def _event_stream(self, session_id: UUID, prompt: str) -> AsyncGenerator[str, None]:
        async with self._db_manager.session() as db:
            async for item in self._service.stream_prompt(db, session_id=session_id, prompt=prompt):
                result = f"data: {json.dumps(item, default=str)}\\n\\n"
                yield result


# Module-level ASGI app is required so uvicorn can import `app` directly.
api_application = ApiApplication(Settings())
app = api_application.app
