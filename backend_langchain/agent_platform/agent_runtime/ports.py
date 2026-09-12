from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol

from .events import AgentEvent


class AgentRuntime(Protocol):
    def run(
        self, *, input: Mapping[str, Any], config: Mapping[str, Any] | None = None
    ) -> AsyncIterator[AgentEvent]: ...


class CheckpointStore(Protocol):
    async def load(self, thread_id: str) -> Mapping[str, Any] | None: ...

    async def save(self, thread_id: str, state: Mapping[str, Any]) -> None: ...
