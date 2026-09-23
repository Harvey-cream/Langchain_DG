from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.db.base import Base


class AnalysisRunModel(Base):
    __tablename__ = 'contract_analysis_runs'
    __table_args__ = (
        Index(
            "uq_contract_active_analysis",
            "version_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'parsing', 'analyzing')"),
            sqlite_where=text("status IN ('pending', 'parsing', 'analyzing')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(ForeignKey('contract_versions.id'), index=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    document_text: Mapped[str] = mapped_column(Text, default='')
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(64), default="contract_review")
    current_step: Mapped[str] = mapped_column(String(64), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v2")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
