from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any


class ClaudeMessageSerializer:
    @classmethod
    def serialize(cls, message: Any) -> dict[str, Any]:
        message_type = type(message).__name__

        if message_type == "UserMessage":
            content = cls._normalize_content(getattr(message, "content", None))
            return {
                "type": message_type,
                "role": "user",
                "content": content,
                "raw": cls._to_jsonable(message),
            }

        if message_type == "AssistantMessage":
            content = cls._normalize_content(getattr(message, "content", None))
            return {
                "type": message_type,
                "role": "assistant",
                "model": getattr(message, "model", None),
                "content": content,
                "raw": cls._to_jsonable(message),
            }

        if message_type == "SystemMessage":
            return {
                "type": message_type,
                "role": "system",
                "subtype": getattr(message, "subtype", "info"),
                "data": cls._to_jsonable(getattr(message, "data", {})),
                "raw": cls._to_jsonable(message),
            }

        if message_type == "ResultMessage":
            return {
                "type": message_type,
                "role": "result",
                "subtype": getattr(message, "subtype", "success"),
                "duration_ms": getattr(message, "duration_ms", None),
                "duration_api_ms": getattr(message, "duration_api_ms", None),
                "num_turns": getattr(message, "num_turns", None),
                "result": getattr(message, "result", ""),
                "is_error": getattr(message, "is_error", False),
                "session_id": getattr(message, "session_id", None),
                "total_cost_usd": getattr(message, "total_cost_usd", None),
                "usage": cls._to_jsonable(getattr(message, "usage", None)),
                "raw": cls._to_jsonable(message),
            }

        if message_type == "StreamEvent":
            return {
                "type": message_type,
                "role": "stream_event",
                "event": getattr(message, "event", None),
                "data": cls._to_jsonable(getattr(message, "data", None)),
                "raw": cls._to_jsonable(message),
            }

        return {
            "type": message_type,
            "role": "unknown",
            "raw": cls._to_jsonable(message),
        }

    @classmethod
    def extract_text(cls, serialized_message: dict[str, Any]) -> str | None:
        role = serialized_message.get("role")
        if role == "user":
            content = serialized_message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = [item.get("text", "") for item in content if isinstance(item, dict)]
                return "\n".join(part for part in texts if part) or None
            return None

        if role == "assistant":
            content = serialized_message.get("content")
            if not isinstance(content, list):
                return None
            texts = [item.get("text", "") for item in content if isinstance(item, dict)]
            return "\n".join(part for part in texts if part) or None

        if role == "result":
            result = serialized_message.get("result")
            return str(result) if result else None

        return None

    @classmethod
    def _normalize_content(cls, content: Any) -> Any:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return [cls._to_jsonable(item) for item in content]
        return cls._to_jsonable(content)

    @classmethod
    def _to_jsonable(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [cls._to_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._to_jsonable(item) for key, item in value.items()}
        if is_dataclass(value):
            return cls._to_jsonable(asdict(value))
        if hasattr(value, "model_dump"):
            return cls._to_jsonable(value.model_dump(mode="json"))
        if hasattr(value, "__dict__"):
            return cls._to_jsonable(vars(value))
        return str(value)
