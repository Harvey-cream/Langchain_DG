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


async def init_db_tables() -> None:
    """启动时创建缺失表，并补齐已有会话表的 status/token 列。"""
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_session_column_patches)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
