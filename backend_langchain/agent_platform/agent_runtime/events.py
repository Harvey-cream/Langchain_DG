from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AgentEventType = Literal[
    "status",
    "delta",
    "interrupt",
    "approval_required",
    "completed",
    "failed",
]


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: AgentEventType
    data: dict[str, Any]

    @classmethod
    def text(cls, text: str) -> "AgentEvent":
        return cls("delta", {"text": text})
