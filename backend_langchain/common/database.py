from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Iterable
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from common.settings import DATABASE_URL

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """用户、面试与合同共用同一份 SQLAlchemy MetaData。"""


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(tables: Iterable[Any]) -> None:
    selected = list(tables)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=selected))


async def apply_column_patches(patches: Iterable[tuple[str, str, str]]) -> None:
    selected = list(patches)

    def _apply(sync_conn) -> None:
        inspector = inspect(sync_conn)
        table_names = set(inspector.get_table_names())
        for table, column, ddl in selected:
            if table not in table_names:
                continue
            existing = {item["name"] for item in inspector.get_columns(table)}
            if column in existing:
                continue
            sync_conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
            logger.info("schema patch: added %s.%s", table, column)

    async with engine.begin() as conn:
        await conn.run_sync(_apply)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
