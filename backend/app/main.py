from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_manager
from app.runtime import ClaudeRuntimeRegistry
from app.schemas import (
    MessageRead,
    PromptRequest,
    SessionCreate,
    SessionLogRead,
    SessionRead,
    UserCreate,
    UserRead,
)
from app.services import ClaudeAgentService

runtime_registry = ClaudeRuntimeRegistry()
service = ClaudeAgentService(runtime_registry)


def ensure_claude_config_files() -> None:
    claude_config_path = Path.home() / ".claude.json"
    claude_dir = Path.home() / ".claude"
    remote_settings_path = claude_dir / "remote-settings.json"

    if not claude_config_path.exists():
        claude_config_path.write_text("{}\n", encoding="utf-8")

    claude_dir.mkdir(parents=True, exist_ok=True)
    if not remote_settings_path.exists():
        remote_settings_path.write_text("{}\n", encoding="utf-8")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    ensure_claude_config_files()

    db_manager = get_database_manager()
    await db_manager.wait_until_available()
    await db_manager.create_tables()

    async for db in db_manager.get_session():
        await service.ensure_default_users(db)
        break

    yield

    await runtime_registry.close_all()


app = FastAPI(title="Claude Agent SDK UI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    db_manager = get_database_manager()
    async for session in db_manager.get_session():
        yield session


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/users", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserRead]:
    users = await service.list_users(db)
    return [UserRead.model_validate(user) for user in users]


@app.post("/api/users", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    user = await service.create_user(db, payload)
    return UserRead.model_validate(user)


@app.get("/api/users/{user_id}/sessions", response_model=list[SessionRead])
async def list_sessions(user_id: UUID, db: AsyncSession = Depends(get_db)) -> list[SessionRead]:
    sessions = await service.list_sessions(db, user_id)
    return [SessionRead.model_validate(session) for session in sessions]


@app.post("/api/sessions", response_model=SessionRead, status_code=201)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)) -> SessionRead:
    session = await service.create_session(db, payload)
    return SessionRead.model_validate(session)


@app.get("/api/sessions/{session_id}", response_model=SessionRead)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> SessionRead:
    session = await service.get_session(db, session_id)
    return SessionRead.model_validate(session)


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageRead])
async def list_messages(session_id: UUID, db: AsyncSession = Depends(get_db)) -> list[MessageRead]:
    messages = await service.list_messages(db, session_id)
    return [MessageRead.model_validate(message) for message in messages]


@app.get("/api/sessions/{session_id}/logs", response_model=list[SessionLogRead])
async def list_logs(session_id: UUID, db: AsyncSession = Depends(get_db)) -> list[SessionLogRead]:
    logs = await service.list_logs(db, session_id)
    return [SessionLogRead.model_validate(log) for log in logs]


@app.post("/api/sessions/{session_id}/interrupt", status_code=204)
async def interrupt_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await service.interrupt_session(db, session_id)


@app.post("/api/sessions/{session_id}/messages/stream")
async def stream_messages(
    session_id: UUID,
    payload: PromptRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    async def event_stream() -> AsyncGenerator[str, None]:
        async for item in service.stream_prompt(db, session_id=session_id, prompt=prompt):
            yield f"data: {json.dumps(item, default=str)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
