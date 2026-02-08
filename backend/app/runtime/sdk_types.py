from __future__ import annotations

try:
    from claude_code_sdk import ClaudeCodeOptions as ClaudeOptions
except ImportError:  # pragma: no cover - compatibility branch
    from claude_code_sdk import ClaudeAgentOptions as ClaudeOptions

from claude_code_sdk import ClaudeSDKClient

__all__ = ["ClaudeOptions", "ClaudeSDKClient"]
