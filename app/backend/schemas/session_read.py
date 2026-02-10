from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    status: str
    model: str
    permission_mode: str
    system_prompt: str | None
    claude_session_id: str | None
    created_at: datetime
    updated_at: datetime
