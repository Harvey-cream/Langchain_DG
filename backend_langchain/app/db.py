from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Contract 表由 Alembic 管理；旧模块仍暂时沿用 create_all 和会话字段补丁。
_SESSION_COLUMN_PATCHES: list[tuple[str, str, str]] = [
    ("user_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("user_sessions", "token_estimate", "INT NULL"),
    ("interview_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("interview_sessions", "token_estimate", "INT NULL"),
]

CONTRACT_TABLE_NAMES = frozenset(
    {
        "contract_customers",
        "contracts",
        "contract_versions",
        "contract_version_contents",
        "contract_analysis_runs",
        "contract_clauses",
        "contract_risks",
        "contract_review_selections",
    }
)


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


def _legacy_tables(metadata):
    return [
        table
        for table in metadata.sorted_tables
        if table.name not in CONTRACT_TABLE_NAMES
    ]


def _contract_runtime_tables_exist(sync_conn) -> bool:
    tables = set(inspect(sync_conn).get_table_names())
    return {"contract_versions", "contract_analysis_runs"}.issubset(tables)


async def init_db_tables() -> None:
    """兼容初始化旧模块表；Contract Schema 必须先由 Alembic 建立。"""
    from app.models import Base
    from infrastructure.db.models.analysis import AnalysisRunModel  # noqa: F401
    from infrastructure.db.models.contract import ContractModel  # noqa: F401
    from infrastructure.db.models.customer import CustomerModel  # noqa: F401
    from infrastructure.db.models.review import (
        ContractClauseModel,
        ContractReviewSelectionModel,
        ContractRiskModel,
        ContractVersionContentModel,
    )
    from infrastructure.db.models.version import ContractVersionModel  # noqa: F401

    async with engine.begin() as conn:
        tables = _legacy_tables(Base.metadata)
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
        await conn.run_sync(_apply_session_column_patches)


async def recover_interrupted_contract_reviews() -> None:
    """Runtime recovery only; this function never creates or alters schema."""
    async with engine.begin() as conn:
        if not await conn.run_sync(_contract_runtime_tables_exist):
            logger.warning(
                "Contract Schema 尚未迁移，跳过中断任务恢复；请先运行 alembic upgrade head"
            )
            return

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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
