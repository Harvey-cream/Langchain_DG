from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Contract:
    id: UUID
    user_id: int
    customer_id: int
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, user_id: int, customer_id: int, title: str) -> "Contract":
        title = title.strip()
        if not title:
            raise ValueError("contract title is required")
        return cls(
            id=uuid4(), user_id=user_id, customer_id=customer_id, title=title
        )
