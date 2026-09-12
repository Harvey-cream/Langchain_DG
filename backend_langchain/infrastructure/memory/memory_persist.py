"""压缩摘要异步落 Postgres conversation_summaries。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.utils import utc_now_naive
from backend_langchain.logger_func import log_exception_event

logger = logging.getLogger(__name__)

AgentKind = Literal["main", "interview"]

# ===========================================================================
# 共用：压缩完成后异步归档（与触发方式是 turn 还是 token 无关）
# ===========================================================================


@dataclass(frozen=True)
class MemoryTurnContext:
    user_id: int
    conversation_id: int
    kind: AgentKind


def schedule_async_summary_persist(
    ctx: MemoryTurnContext,
    *,
    summary: str,
    turn_count: int,
    token_estimate: int,
) -> None:
    text = (summary or "").strip()
    if not text:
        return

    async def _run() -> None:
        from app.db import SessionLocal
        from app.models import ConversationSummary

        now = utc_now_naive()
        try:
            async with SessionLocal() as session:
                stmt = pg_insert(ConversationSummary).values(
                    user_id=ctx.user_id,
                    conversation_id=ctx.conversation_id,
                    kind=ctx.kind,
                    summary=text,
                    turn_count_at_compress=turn_count,
                    token_estimate=token_estimate,
                    updated_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["kind", "conversation_id"],
                    set_={
                        "summary": stmt.excluded.summary,
                        "turn_count_at_compress": stmt.excluded.turn_count_at_compress,
                        "token_estimate": stmt.excluded.token_estimate,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:  # noqa: BLE001
            log_exception_event(
                logger,
                "async_summary_persist_failed",
                user_id=ctx.user_id,
                conversation_id=ctx.conversation_id,
                kind=ctx.kind,
            )

    asyncio.create_task(_run())
