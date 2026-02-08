from __future__ import annotations

from app.core import PermissionMode, settings


def default_permission_mode() -> str:
    if settings.claude_permission_mode == PermissionMode.BYPASS_PERMISSIONS:
        return PermissionMode.BYPASS_PERMISSIONS.value
    return settings.claude_permission_mode.value
