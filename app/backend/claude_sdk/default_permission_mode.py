from __future__ import annotations

from app.backend.core.permission_mode import PermissionMode
from app.backend.core.settings import Settings


class DefaultPermissionModeResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self) -> str:
        if self._settings.claude_permission_mode == PermissionMode.BYPASS_PERMISSIONS:
            result = PermissionMode.BYPASS_PERMISSIONS.value
            return result
        result = self._settings.claude_permission_mode.value
        return result
