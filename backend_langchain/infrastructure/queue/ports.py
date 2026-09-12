from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class JobMessage:
    job_type: str
    payload: dict[str, Any]
    job_id: str = field(default_factory=lambda: str(uuid4()))
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobQueue(Protocol):
    async def enqueue(self, message: JobMessage) -> str: ...


class WorkerHandler(Protocol):
    async def handle(self, message: JobMessage) -> None: ...
