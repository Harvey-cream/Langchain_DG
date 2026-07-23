"""LangGraph checkpoint：独立 PostgreSQL 库（默认 langchain_checkpoint）。"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_checkpointer: Any | None = None
_checkpointer_ctx: Any = None


async def _ensure_checkpoint_database() -> None:
    """确保 checkpoint 独立库存在（连默认 postgres 库执行 CREATE DATABASE）。"""
    import asyncpg

    from app.settings import (
        POSTGRES_CHECKPOINT_DATABASE,
        POSTGRES_HOST,
        POSTGRES_PASSWORD,
        POSTGRES_PORT,
        POSTGRES_USER,
    )

    db = POSTGRES_CHECKPOINT_DATABASE
    conn = await asyncpg.connect(
        host=POSTGRES_HOST,
        port=int(POSTGRES_PORT),
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db
        )
        if not exists:
            # CREATE DATABASE 不能在事务块内执行；asyncpg.execute 默认非事务
            await conn.execute(f'CREATE DATABASE "{db}"')
            logger.info("checkpoint database created: %s", db)
    finally:
        await conn.close()


async def init_checkpointer() -> Any:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer is None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from app.settings import CHECKPOINT_POSTGRES_URL, POSTGRES_CHECKPOINT_DATABASE

        await _ensure_checkpoint_database()
        _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(CHECKPOINT_POSTGRES_URL)
        _checkpointer = await _checkpointer_ctx.__aenter__()
        # setup() 幂等：建表 / 迁移，已存在则跳过
        await _checkpointer.setup()
        logger.info("langgraph checkpointer ready db=%s", POSTGRES_CHECKPOINT_DATABASE)
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
    _checkpointer = None
    _checkpointer_ctx = None


def get_checkpointer() -> Any:
    if _checkpointer is None:
        raise RuntimeError("checkpointer 未初始化，请在应用 lifespan 中调用 init_checkpointer()")
    return _checkpointer


def agent_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"agent:{user_id}:{conversation_id}"


def interview_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"interview:{user_id}:{conversation_id}"
