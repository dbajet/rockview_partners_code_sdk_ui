from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Constants:
    # Message types
    MESSAGE_TYPE_USER: str = "UserMessage"
    MESSAGE_TYPE_ASSISTANT: str = "AssistantMessage"
    MESSAGE_TYPE_SYSTEM: str = "SystemMessage"
    MESSAGE_TYPE_RESULT: str = "ResultMessage"
    MESSAGE_TYPE_STREAM_EVENT: str = "StreamEvent"
    MESSAGE_TYPE_PROMPT: str = "prompt"
    MESSAGE_TYPE_UNKNOWN: str = "Unknown"

    # Roles
    ROLE_USER: str = "user"
    ROLE_ASSISTANT: str = "assistant"
    ROLE_SYSTEM: str = "system"
    ROLE_RESULT: str = "result"
    ROLE_STREAM_EVENT: str = "stream_event"
    ROLE_UNKNOWN: str = "unknown"

    # Stream envelope events
    STREAM_EVENT_MESSAGE: str = "message"
    STREAM_EVENT_ERROR: str = "error"

    # Session events and status
    SESSION_EVENT_CREATED: str = "SESSION_CREATED"
    SESSION_EVENT_INTERRUPTED: str = "SESSION_INTERRUPTED"
    SESSION_EVENT_PROMPT_SUBMITTED: str = "PROMPT_SUBMITTED"
    SESSION_EVENT_TURN_RESULT: str = "TURN_RESULT"
    SESSION_EVENT_SDK_ERROR: str = "SDK_ERROR"
    SESSION_EVENT_WAITING_USER_ANSWER: str = "WAITING_USER_ANSWER"
    SESSION_STATUS_ERROR: str = "error"
    SESSION_SOURCE_UI: str = "ui"

    # Serializer defaults
    SYSTEM_SUBTYPE_INFO: str = "info"
    RESULT_SUBTYPE_SUCCESS: str = "success"

    # Runtime retry behavior
    RUNTIME_MAX_ATTEMPTS: int = 3
    RUNTIME_RETRY_BASE_DELAY_SECONDS: float = 1.0
    RUNTIME_RETRY_TOKEN_INITIALIZE: str = "initialize"
    RUNTIME_RETRY_TOKEN_TIMEOUT: str = "timeout"
    RUNTIME_RETRY_TOKEN_CONTROL_REQUEST_TIMEOUT: str = "control request timeout"
    RUNTIME_RETRY_TOKEN_EXIT_CODE_1: str = "command failed with exit code 1"

    # Tool names
    TOOL_ASK_USER_QUESTION: str = "AskUserQuestion"


Constants = _Constants()
