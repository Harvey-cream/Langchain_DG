from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from infrastructure.db.base import Base


class AnalysisRunModel(Base):
    __tablename__ = 'contract_analysis_runs'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(ForeignKey('contract_versions.id'), index=True)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    document_text: Mapped[str] = mapped_column(Text, default='')
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
