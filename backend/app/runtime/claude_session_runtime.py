from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from inspect import isawaitable
from typing import Any

from app.core import settings
from app.core.constants import Constants
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

        self._query_lock = asyncio.Lock()
        self._active_client_lock = asyncio.Lock()
        self._active_client: ClaudeSDKClient | None = None

    async def query_stream(self, prompt: str) -> AsyncGenerator[Any, None]:
        async with self._query_lock:
            max_attempts = Constants.RUNTIME_MAX_ATTEMPTS
            last_error: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                client = ClaudeSDKClient(options=self._build_options())
                await client.connect()
                await self._set_active_client(client)
                emitted_count = 0

                try:
                    query_result = client.query(prompt)
                    if hasattr(query_result, "__aiter__"):
                        async for message in query_result:
                            emitted_count += 1
                            yield message
                            if type(message).__name__ == Constants.MESSAGE_TYPE_RESULT:
                                break
                        return

                    if isawaitable(query_result):
                        await query_result

                    response_reader = client.receive_response()
                    if hasattr(response_reader, "__aiter__"):
                        saw_result = False
                        async for message in response_reader:
                            emitted_count += 1
                            yield message
                            if type(message).__name__ == Constants.MESSAGE_TYPE_RESULT:
                                saw_result = True
                                break
                        if not saw_result:
                            print("[runtime] warning: stream ended without ResultMessage", flush=True)
                        return

                    while True:
                        message = client.receive_response()
                        if isawaitable(message):
                            message = await message
                        emitted_count += 1
                        yield message
                        if type(message).__name__ == Constants.MESSAGE_TYPE_RESULT:
                            break
                    return
                except Exception as exc:
                    last_error = exc
                    retryable = self._is_retryable_startup_error(exc) and emitted_count == 0
                    if retryable and attempt < max_attempts:
                        print(
                            f"[runtime] transient SDK startup failure (attempt {attempt}/{max_attempts})"
                            f" type={type(exc).__name__} message={exc}",
                            flush=True,
                        )
                        await asyncio.sleep(Constants.RUNTIME_RETRY_BASE_DELAY_SECONDS * attempt)
                        continue
                    raise
                finally:
                    await self._clear_active_client(client)
                    if hasattr(client, "disconnect"):
                        disconnect_method = getattr(client, "disconnect")
                        result = disconnect_method()
                        if asyncio.iscoroutine(result):
                            try:
                                await result
                            except RuntimeError as exc:
                                print(f"[runtime] disconnect warning: {exc}", flush=True)

            if last_error is not None:
                raise last_error

    async def interrupt(self) -> None:
        async with self._active_client_lock:
            client = self._active_client
        if client is not None:
            await client.interrupt()

    async def close(self) -> None:
        await self.interrupt()

    def set_resume(self, claude_session_id: str | None) -> None:
        if claude_session_id:
            self.resume = claude_session_id

    async def _set_active_client(self, client: ClaudeSDKClient) -> None:
        async with self._active_client_lock:
            self._active_client = client

    async def _clear_active_client(self, client: ClaudeSDKClient) -> None:
        async with self._active_client_lock:
            if self._active_client is client:
                self._active_client = None

    def _build_options(self) -> ClaudeOptions:
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
        if settings.claude_debug_stderr:
            options_kwargs["extra_args"] = {"debug-to-stderr": None}
        return ClaudeOptions(**options_kwargs)

    @staticmethod
    def _is_retryable_startup_error(exc: Exception) -> bool:
        message = str(exc).lower()
        is_initialize_timeout = (
            Constants.RUNTIME_RETRY_TOKEN_INITIALIZE in message
            and Constants.RUNTIME_RETRY_TOKEN_TIMEOUT in message
        )
        is_control_timeout = Constants.RUNTIME_RETRY_TOKEN_CONTROL_REQUEST_TIMEOUT in message
        is_process_exit_1 = Constants.RUNTIME_RETRY_TOKEN_EXIT_CODE_1 in message
        return is_initialize_timeout or is_control_timeout or is_process_exit_1
