from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from inspect import isawaitable
from typing import Any

from app.runtime.sdk_types import ClaudeOptions, ClaudeSDKClient


class ClaudeSessionRuntime:
    def __init__(
        self,
        *,
        model: str,
        permission_mode: str,
        max_turns: int,
        system_prompt: str | None,
        allowed_tools: list[str] | None,
        resume: str | None,
    ) -> None:
        self.model = model
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.resume = resume

        self._client_lock = asyncio.Lock()
        self._query_lock = asyncio.Lock()
        self._client: ClaudeSDKClient | None = None

    async def query_stream(self, prompt: str) -> AsyncGenerator[Any, None]:
        async with self._query_lock:
            client = await self._get_client()

            query_result = client.query(prompt)
            if hasattr(query_result, "__aiter__"):
                async for message in query_result:
                    yield message
                    if type(message).__name__ == "ResultMessage":
                        break
                return

            if isawaitable(query_result):
                await query_result

            response_reader = client.receive_response()
            if hasattr(response_reader, "__aiter__"):
                async for message in response_reader:
                    yield message
                    if type(message).__name__ == "ResultMessage":
                        break
                return

            while True:
                message = client.receive_response()
                if isawaitable(message):
                    message = await message
                yield message
                if type(message).__name__ == "ResultMessage":
                    break

    async def interrupt(self) -> None:
        if self._client is not None:
            await self._client.interrupt()

    async def close(self) -> None:
        async with self._client_lock:
            if self._client is None:
                return
            if hasattr(self._client, "disconnect"):
                disconnect_method = getattr(self._client, "disconnect")
                result = disconnect_method()
                if asyncio.iscoroutine(result):
                    try:
                        await result
                    except RuntimeError as exc:
                        # Some SDK versions bind disconnect scopes to the task that created the query.
                        # During app reload/shutdown this can run in another task; ignore that shutdown-only error.
                        print(f"[runtime] disconnect warning: {exc}", flush=True)
            self._client = None

    def set_resume(self, claude_session_id: str | None) -> None:
        if claude_session_id:
            self.resume = claude_session_id

    async def _get_client(self) -> ClaudeSDKClient:
        async with self._client_lock:
            if self._client is None:
                options_kwargs: dict[str, Any] = {
                    "model": self.model,
                    "permission_mode": self.permission_mode,
                    "max_turns": self.max_turns,
                }
                if self.allowed_tools:
                    options_kwargs["allowed_tools"] = self.allowed_tools
                if self.system_prompt:
                    options_kwargs["system_prompt"] = self.system_prompt
                if self.resume:
                    options_kwargs["resume"] = self.resume

                options = ClaudeOptions(**options_kwargs)
                self._client = ClaudeSDKClient(options=options)
                await self._client.connect()

            return self._client
