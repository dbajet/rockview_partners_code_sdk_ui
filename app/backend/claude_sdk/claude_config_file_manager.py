from __future__ import annotations

import logging
from pathlib import Path


class ClaudeConfigFileManager:
    @classmethod
    def ensure_files(cls) -> None:
        claude_config_path = Path.home() / ".claude.json"
        claude_dir = Path.home() / ".claude"
        remote_settings_path = claude_dir / "remote-settings.json"

        try:
            if not claude_config_path.exists():
                claude_config_path.write_text("{}\n", encoding="utf-8")
            claude_dir.mkdir(parents=True, exist_ok=True)
            if not remote_settings_path.exists():
                remote_settings_path.write_text("{}\n", encoding="utf-8")
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "[runtime] warning: unable to ensure Claude config files: %s",
                exc,
            )
