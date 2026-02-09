from __future__ import annotations

import asyncio

from app.core import settings
from app.runtime.claude_session_runtime import ClaudeSessionRuntime


class ClaudeRuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, ClaudeSessionRuntime] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        *,
        local_session_id: str,
        model: str,
        permission_mode: str,
        max_turns: int,
        system_prompt: str | None,
        resume: str | None,
    ) -> ClaudeSessionRuntime:
        async with self._lock:
            runtime = self._runtimes.get(local_session_id)
            if runtime is None:
                runtime = ClaudeSessionRuntime(
                    model=model,
                    permission_mode=permission_mode,
                    max_turns=max_turns,
                    system_prompt=system_prompt,
                    allowed_tools=settings.claude_allowed_tools,
                    resume=resume,
                )
                self._runtimes[local_session_id] = runtime
            else:
                runtime.set_resume(resume)
            return runtime

    async def interrupt(self, local_session_id: str) -> None:
        runtime = self._runtimes.get(local_session_id)
        if runtime is None:
            return
        await runtime.interrupt()

    async def drop(self, local_session_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(local_session_id, None)
        if runtime is not None:
            await runtime.close()

    async def close_all(self) -> None:
        async with self._lock:
            runtimes = list(self._runtimes.values())
            self._runtimes.clear()

        for runtime in runtimes:
            await runtime.close()
