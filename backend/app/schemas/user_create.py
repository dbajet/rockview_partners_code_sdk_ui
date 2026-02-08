from __future__ import annotations

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
