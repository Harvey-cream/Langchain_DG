from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Customer:
    id: int | None
    user_id: int
    name: str
    email: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, user_id: int, name: str, email: str) -> "Customer":
        name = name.strip()
        email = email.strip()
        if not name:
            raise ValueError("customer name is required")
        if not email or "@" not in email:
            raise ValueError("valid customer email is required")
        return cls(id=None, user_id=user_id, name=name, email=email)
