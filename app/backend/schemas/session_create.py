from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    user_id: UUID
    title: str | None = Field(default=None, max_length=160)
    model: str | None = None
    system_prompt: str | None = None
    permission_mode: str | None = None
