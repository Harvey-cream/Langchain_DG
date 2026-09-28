"""SQLAlchemy models owned by the Contract product."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.database import Base


class CustomerModel(Base):
    __tablename__ = "contract_customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ContractModel(Base):
    __tablename__ = "contracts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("contract_customers.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ContractVersionModel(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "number", name="uq_contract_version_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    source_key: Mapped[str] = mapped_column(String(1024))
    filename: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContractVersionContentModel(Base):
    __tablename__ = "contract_version_contents"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), primary_key=True
    )
    document_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    parser_name: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(32), default="v1")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AnalysisRunModel(Base):
    __tablename__ = "contract_analysis_runs"
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
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    document_text: Mapped[str] = mapped_column(Text, default="")
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


class ContractClauseModel(Base):
    __tablename__ = "contract_clauses"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_contract_clause_run_sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    clause_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    original_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    locator: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContractRiskModel(Base):
    __tablename__ = "contract_risks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_analysis_runs.id", ondelete="CASCADE"), index=True
    )
    clause_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contract_clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    evidence_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ContractReviewSelectionModel(Base):
    __tablename__ = "contract_review_selections"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), primary_key=True
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_analysis_runs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ContractDocumentBlockModel(Base):
    __tablename__ = "contract_document_blocks"
    __table_args__ = (
        UniqueConstraint(
            "version_id", "sequence", name="uq_contract_block_version_sequence"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CanonicalContractClauseModel(Base):
    __tablename__ = "contract_document_clauses"
    __table_args__ = (
        UniqueConstraint(
            "version_id", "sequence", name="uq_contract_document_clause_sequence"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    clause_type: Mapped[str] = mapped_column(String(64))
    original_text: Mapped[str] = mapped_column(Text)
    source_block_ids: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    pages: Mapped[list[int]] = mapped_column(JSON)
    intelligence_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContractDocumentFactsModel(Base):
    __tablename__ = "contract_document_facts"

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_versions.id", ondelete="CASCADE"), primary_key=True
    )
    parser_version: Mapped[str] = mapped_column(String(32))
    intelligence_version: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64))
    extracted_metadata: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    covered_blocks: Mapped[int] = mapped_column(Integer)
    total_blocks: Mapped[int] = mapped_column(Integer)
    coverage_ratio: Mapped[float] = mapped_column(Float)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


CONTRACT_TABLES = (
    CustomerModel.__table__,
    ContractModel.__table__,
    ContractVersionModel.__table__,
    ContractVersionContentModel.__table__,
    AnalysisRunModel.__table__,
    ContractClauseModel.__table__,
    ContractRiskModel.__table__,
    ContractReviewSelectionModel.__table__,
    ContractDocumentBlockModel.__table__,
    CanonicalContractClauseModel.__table__,
    ContractDocumentFactsModel.__table__,
)
CONTRACT_TABLE_NAMES = frozenset(table.name for table in CONTRACT_TABLES)
