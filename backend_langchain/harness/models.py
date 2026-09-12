from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AgentRun:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    product: str = ""
    workflow: str = ""
    status: str = "created"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)

    def finish(self, *, status: str = "completed") -> None:
        self.status = status
        self.finished_at = datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class TraceSpan:
    name: str
    started_at: datetime
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trace:
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    spans: list[TraceSpan] = field(default_factory=list)
