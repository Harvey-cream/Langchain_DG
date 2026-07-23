"""LangGraph checkpoint：独立 MySQL 库（默认 langchain_checkpoint）。"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_checkpointer: Any | None = None
_checkpointer_ctx: Any = None


async def _ensure_checkpoint_database() -> None:
    """确保 checkpoint 独立库存在，并统一为 utf8mb4_0900_ai_ci（MySQL 8 默认）。"""
    import asyncmy

    from app.settings import (
        MYSQL_CHECKPOINT_DATABASE,
        MYSQL_HOST,
        MYSQL_PASSWORD,
        MYSQL_PORT,
        MYSQL_USER,
    )

    db = MYSQL_CHECKPOINT_DATABASE
    collate = "utf8mb4_0900_ai_ci"
    conn = await asyncmy.connect(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        autocommit=True,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                (db,),
            )
            if await cur.fetchone() is None:
                await cur.execute(
                    f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE {collate}"
                )
            await cur.execute(
                "SELECT DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
                "WHERE SCHEMA_NAME=%s",
                (db,),
            )
            row = await cur.fetchone()
            current = (row[0] if row else "") or ""
            if current != collate:
                await cur.execute(
                    f"ALTER DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE {collate}"
                )
                await cur.execute(f"USE `{db}`")
                await cur.execute("SHOW TABLES")
                for (table_name,) in await cur.fetchall():
                    await cur.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                logger.info(
                    "checkpoint db collation migrated to %s (tables recreated on setup)",
                    collate,
                )
    finally:
        conn.close()


async def _checkpoint_schema_ready() -> bool:
    """checkpoint 表是否已建好（避免重复 setup 报 already exists）。"""
    import asyncmy

    from app.settings import (
        MYSQL_CHECKPOINT_DATABASE,
        MYSQL_HOST,
        MYSQL_PASSWORD,
        MYSQL_PORT,
        MYSQL_USER,
    )

    conn = await asyncmy.connect(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_CHECKPOINT_DATABASE,
        autocommit=True,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='checkpoints' LIMIT 1",
                (MYSQL_CHECKPOINT_DATABASE,),
            )
            return await cur.fetchone() is not None
    finally:
        conn.close()


async def init_checkpointer() -> Any:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer is None:
        from langgraph.checkpoint.mysql.asyncmy import AsyncMySaver

        from app.settings import CHECKPOINT_MYSQL_URL, MYSQL_CHECKPOINT_DATABASE

        await _ensure_checkpoint_database()
        _checkpointer_ctx = AsyncMySaver.from_conn_string(CHECKPOINT_MYSQL_URL)
        _checkpointer = await _checkpointer_ctx.__aenter__()
        if not await _checkpoint_schema_ready():
            await _checkpointer.setup()
        logger.info("langgraph checkpointer ready db=%s", MYSQL_CHECKPOINT_DATABASE)
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
