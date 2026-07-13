import logging
import os
from typing import Any

from langchain_core.messages import RemoveMessage
from langgraph.graph.state import CompiledStateGraph

from Agent_memory.memory_persist import MemoryTurnContext, schedule_async_summary_persist
from Agent_memory.token_budget import estimate_messages_tokens
from backend_langchain.logger_func import log_info_event, log_warning_event

logger = logging.getLogger(__name__)


# ===========================================================================
# 总开关
# ===========================================================================

def _memory_compression_enabled() -> bool:
    raw = (os.getenv("MEMORY_COMPRESSION_ENABLED", "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# ===========================================================================
# Turn 压缩：配置（轮次上限 MEMORY_MAX_TURNS、热区保留 MEMORY_KEEP_LAST_TURNS）
# ===========================================================================

def _memory_keep_last_turns() -> int:
    raw = (os.getenv("MEMORY_KEEP_LAST_TURNS", "6") or "6").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 6


def _memory_max_turns_before_compress() -> int:
    raw = (os.getenv("MEMORY_MAX_TURNS", "12") or "12").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 12
    return max(_memory_keep_last_turns() + 1, n)


def _memory_min_overflow_turns() -> int:
    raw = (os.getenv("MEMORY_MIN_OVERFLOW_TURNS", "1") or "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


# ===========================================================================
# Token 压缩：配置（MEMORY_TOKEN_BUDGET；未设时可用 CONTEXT_TOKENS × RATIO 推算）
# ===========================================================================

def _memory_token_budget() -> int:
    """历史 messages 超过此估算 token 即触发压缩（默认 30k）。"""
    direct = (os.getenv("MEMORY_TOKEN_BUDGET", "30000") or "30000").strip()
    try:
        return max(4096, int(direct))
    except ValueError:
        pass
    ctx = _memory_context_tokens()
    return int(ctx * _memory_compress_trigger_ratio())


def _memory_context_tokens() -> int:
    raw = (os.getenv("MEMORY_CONTEXT_TOKENS", "40000") or "40000").strip()
    try:
        return max(4096, int(raw))
    except ValueError:
        return 40000


def _memory_compress_trigger_ratio() -> float:
    raw = (os.getenv("MEMORY_COMPRESS_TRIGGER_RATIO", "0.75") or "0.75").strip()
    try:
        return min(0.95, max(0.3, float(raw)))
    except ValueError:
        return 0.75


# ===========================================================================
# 共用：安全闸 + 双触发判定（turn 条数 OR token 预算，满足其一进入后续流水线）
# ===========================================================================

def _graph_has_pending_work(snapshot: Any) -> bool:
    nxt = getattr(snapshot, "next", None) or ()
    return bool(nxt)


def _should_compress(*, total_turns: int, max_turns: int, token_count: int, token_budget: int) -> bool:
    # Turn 触发：完整轮次数超过上限
    if total_turns > max_turns:
        return True
    # Token 触发：估算 token 超过预算
    return token_count > token_budget


# ===========================================================================
# 主编排：maybe_compress_history
#   Turn 触发 → total_turns > MEMORY_MAX_TURNS
#   Token 触发 → token_count > MEMORY_TOKEN_BUDGET
#   触发后共用：turn 边界裁剪 → LLM 摘要 → 写回 SQLite → 可选 MySQL
# ===========================================================================

async def maybe_compress_history(
    agent: CompiledStateGraph,
    *,
    thread_id: str,
    memory: MemoryTurnContext | None = None,
) -> None:
    """
    stream 前：按 turn 边界 + token 预算压缩；未完成 turn / interrupt 不压。
    摘要写回 SQLite checkpoint；可选异步落 MySQL conversation_summaries。
    """
    if not _memory_compression_enabled():
        return

    from Agent_memory.memory_summary import (
        build_summary_system_message,
        extract_summary_text,
        summarize_overflow,
    )
    from Agent_memory.memory_trim import (
        is_memory_summary,
        partition_turns_by_completeness,
        split_messages_into_turns,
    )

    keep_k = _memory_keep_last_turns()
    max_turns = _memory_max_turns_before_compress()
    min_overflow = _memory_min_overflow_turns()
    token_budget = _memory_token_budget()

    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = await agent.aget_state(config)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_get_state_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return

    if _graph_has_pending_work(snapshot):
        log_info_event(logger, "memory_compress_skipped_pending", thread_id=thread_id)
        return

    state_values = getattr(snapshot, "values", None) or {}
    messages = list(state_values.get("messages") or [])
    if not messages:
        return

    # --- Token 域：估算整段 messages token（触发条件之一）---
    token_count = estimate_messages_tokens(messages)
    # --- Turn 域：切分轮次（触发条件之二 + 后续裁剪单位）---
    leading, turns = split_messages_into_turns(messages)
    total_turns = len(turns)
    # --- 双触发判定：turn 条数 OR token 预算 ---
    if not _should_compress(
        total_turns=total_turns,
        max_turns=max_turns,
        token_count=token_count,
        token_budget=token_budget,
    ):
        return

    # --- Turn 域：末尾未完成轮不进 overflow ---
    complete_turns, incomplete_tail = partition_turns_by_completeness(turns)
    if not complete_turns:
        log_info_event(logger, "memory_compress_skipped_incomplete", thread_id=thread_id)
        return

    # --- Turn 域：保留最近 keep_k 个完整 turn，其余为 overflow ---
    effective_keep = keep_k
    # --- Token 域补丁：token 已超预算但完整轮数 ≤ keep_k 时，强制多溢出 1 轮 ---
    if token_count > token_budget and len(complete_turns) <= effective_keep and len(complete_turns) > 1:
        effective_keep = max(1, len(complete_turns) - 1)

    overflow_turns = (
        complete_turns[:-effective_keep] if len(complete_turns) > effective_keep else []
    )
    kept_complete = (
        complete_turns[-effective_keep:] if overflow_turns else complete_turns
    )

    if len(overflow_turns) < min_overflow:
        return

    overflow_msgs: list[Any] = []
    for t in overflow_turns:
        overflow_msgs.extend(t)

    # --- 共用：从 leading 取出旧摘要，供 rolling 合并 ---
    prev_summary = ""
    other_leading: list[Any] = []
    for m in leading:
        if is_memory_summary(m):
            prev_summary = extract_summary_text(m)
        else:
            other_leading.append(m)

    log_info_event(
        logger,
        "memory_compress_start",
        thread_id=thread_id,
        total_turns=total_turns,
        overflow_turns=len(overflow_turns),
        keep_turns=len(kept_complete),
        token_count=token_count,
        token_budget=token_budget,
        has_prev_summary=bool(prev_summary),
        incomplete_tail_msgs=len(incomplete_tail),
    )

    # --- 共用：LLM 摘要 overflow ---
    try:
        new_summary = summarize_overflow(overflow_msgs, previous_summary=prev_summary)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_summarize_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return

    if not (new_summary or "").strip():
        log_warning_event(logger, "memory_compress_summary_empty", thread_id=thread_id)
        return

    # --- 共用：整表替换 checkpoint messages（SQLite）---
    removes: list[Any] = []
    for m in messages:
        mid = getattr(m, "id", None)
        if mid:
            removes.append(RemoveMessage(id=mid))

    summary_msg = build_summary_system_message(new_summary)
    new_msgs: list[Any] = []
    new_msgs.extend(other_leading)
    new_msgs.append(summary_msg)
    for t in kept_complete:
        new_msgs.extend(t)
    new_msgs.extend(incomplete_tail)

    try:
        await agent.aupdate_state(config, {"messages": removes + new_msgs})
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_update_state_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return

    log_info_event(
        logger,
        "memory_compress_done",
        thread_id=thread_id,
        removed_messages=len(removes),
        kept_turns=len(kept_complete),
        summary_chars=len(new_summary),
    )

    # --- 共用：异步落 MySQL conversation_summaries ---
    if memory is not None:
        schedule_async_summary_persist(
            memory,
            summary=new_summary,
            turn_count=total_turns,
            token_estimate=token_count,
        )
