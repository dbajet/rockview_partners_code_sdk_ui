from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.permission_mode import PermissionMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Claude Agent SDK UI"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://claude_user:claude_pass@db:5432/claude_ui"

    claude_model: str = "claude-sonnet-4-5"
    claude_max_turns: int = 16
    claude_permission_mode: PermissionMode = PermissionMode.BYPASS_PERMISSIONS
    claude_system_prompt: Optional[str] = None
    claude_allowed_tools: Optional[list[str]] = None
    claude_debug_stderr: bool = False

    default_users_csv: str = "demo:Demo User,analyst:Analyst User"

    @field_validator("claude_allowed_tools", mode="before")
    @classmethod
    def _parse_allowed_tools(cls, value: str | list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return parts or None
        return None


settings = Settings()
