from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base


class ContractVersionModel(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint(
            "contract_id", "number", name="uq_contract_version_number"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    contract_id: Mapped[UUID] = mapped_column(ForeignKey("contracts.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    source_key: Mapped[str] = mapped_column(String(1024))
    filename: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
