from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# create_all 不改已有表；启动时补齐会话落库字段
_SESSION_COLUMN_PATCHES: list[tuple[str, str, str]] = [
    ("user_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("user_sessions", "token_estimate", "INT NULL"),
    ("interview_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("interview_sessions", "token_estimate", "INT NULL"),
]

_CONTRACT_ANALYSIS_COLUMN_PATCHES: list[tuple[str, str]] = [
    ("workflow_name", "VARCHAR(64) NOT NULL DEFAULT 'contract_review'"),
    ("current_step", "VARCHAR(64) NOT NULL DEFAULT 'queued'"),
    ("attempt", "INT NOT NULL DEFAULT 1"),
    ("model_name", "VARCHAR(128) NULL"),
    ("prompt_version", "VARCHAR(32) NOT NULL DEFAULT 'v1'"),
    ("started_at", "TIMESTAMP NULL"),
]


def _apply_session_column_patches(sync_conn) -> None:
    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    for table, column, ddl in _SESSION_COLUMN_PATCHES:
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if column in existing:
            continue
        sync_conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
        logger.info("schema patch: added %s.%s", table, column)


def _apply_contract_analysis_column_patches(sync_conn) -> None:
    insp = inspect(sync_conn)
    if "contract_analysis_runs" not in set(insp.get_table_names()):
        return
    existing = {column["name"] for column in insp.get_columns("contract_analysis_runs")}
    for column, ddl in _CONTRACT_ANALYSIS_COLUMN_PATCHES:
        if column in existing:
            continue
        sync_conn.execute(
            text(f'ALTER TABLE "contract_analysis_runs" ADD COLUMN "{column}" {ddl}')
        )
        logger.info("schema patch: added contract_analysis_runs.%s", column)


async def init_db_tables() -> None:
    """启动时创建缺失表，并补齐已有会话表的 status/token 列。"""
    from app.models import Base
    from infrastructure.db.models.analysis import AnalysisRunModel
    from infrastructure.db.models.review import (
        ContractClauseModel,
        ContractReviewSelectionModel,
        ContractRiskModel,
        ContractVersionContentModel,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_session_column_patches)
        await conn.run_sync(_apply_contract_analysis_column_patches)
        await conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_version_number ON contract_versions (contract_id, number)'))
        # Demo uses a single API process. Interrupted jobs become retryable after restart.
        interrupted = "('pending','parsing','analyzing')"
        await conn.execute(
            text(
                "UPDATE contract_versions SET status='failed' "
                "WHERE id IN (SELECT version_id FROM contract_analysis_runs "
                f"WHERE status IN {interrupted})"
            )
        )
        await conn.execute(
            text(
                "UPDATE contract_analysis_runs SET status='failed', "
                "error='服务重启中断了分析，请重新分析', "
                "finished_at=COALESCE(finished_at, CURRENT_TIMESTAMP) "
                f"WHERE status IN {interrupted}"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_active_analysis "
                "ON contract_analysis_runs (version_id) "
                "WHERE status IN ('pending','parsing','analyzing')"
            )
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
