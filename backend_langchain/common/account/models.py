from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from common.database import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(150))
    password: Mapped[str] = mapped_column(String(255))
    display_tag: Mapped[str | None] = mapped_column(String(6), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), onupdate=func.now()
    )


async def ensure_display_tag(session, user: User) -> str:
    if user.display_tag:
        return user.display_tag
    for _ in range(256):
        user.display_tag = f"{secrets.randbelow(1_000_000):06d}"
        try:
            await session.commit()
            await session.refresh(user)
            return user.display_tag
        except IntegrityError:
            await session.rollback()
            user.display_tag = None
    raise RuntimeError("无法为用户分配 display_tag")
