import logging
import os
from typing import Any

from langchain_core.messages import RemoveMessage
from langgraph.graph.state import CompiledStateGraph

from backend_langchain.logger_func import log_info_event, log_warning_event

logger = logging.getLogger(__name__)


def _memory_compression_enabled() -> bool:
    raw = (os.getenv("MEMORY_COMPRESSION_ENABLED", "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _memory_keep_last_turns() -> int:
    """裁剪后保留的最近 turn 数（短期记忆窗口）。"""
    raw = (os.getenv("MEMORY_KEEP_LAST_TURNS", "20") or "20").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 20


def _memory_max_turns_before_compress() -> int:
    """触发压缩的 turn 数上限（必须 > KEEP_LAST_TURNS，避免抖动）。"""
    raw = (os.getenv("MEMORY_MAX_TURNS", "25") or "25").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 25
    return max(_memory_keep_last_turns() + 1, n)


def _memory_min_overflow_turns() -> int:
    """触发压缩时溢出至少这么多 turn 才动手（避免 1 条溢出就摘要一次，节流）。"""
    raw = (os.getenv("MEMORY_MIN_OVERFLOW_TURNS", "5") or "5").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def maybe_compress_history(
    agent: CompiledStateGraph,
    *,
    thread_id: str,
) -> None:
    """
    在 invoke / stream 之前调用：检查 checkpoint 中 messages 的 turn 数；
    超阈值则用同一 LLM 生成新摘要，重写 state 并写回 checkpoint。

    设计：
    - 短期记忆：保留最后 KEEP 个完整 turn（按 HumanMessage 起切，永远不切断 tool 闭环）
    - 长期记忆：之前 overflow + 既有摘要 → 滚动合并为新的 SystemMessage（带特殊标记）
    - 失败回滚：任意环节抛错都不修改 state，记一条 warning 日志即可

    任何异常都吞掉（仅记日志），不影响主对话流程。
    """
    if not _memory_compression_enabled():
        return

    # 延迟 import，避免循环依赖与无谓加载
    from Agent_memory.memory_summary import (
        build_summary_system_message,
        extract_summary_text,
        summarize_overflow,
    )
    from Agent_memory.memory_trim import (
        is_memory_summary,
        split_messages_into_turns,
        trim_to_last_k_turns,
    )

    keep_k = _memory_keep_last_turns()
    max_turns = _memory_max_turns_before_compress()
    min_overflow = _memory_min_overflow_turns()

    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = agent.get_state(config)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_get_state_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return

    state_values = getattr(snapshot, "values", None) or {}
    messages = list(state_values.get("messages") or [])
    if not messages:
        return

    leading, turns = split_messages_into_turns(messages)
    total_turns = len(turns)
    if total_turns <= max_turns:
        return
    overflow_count = total_turns - keep_k
    if overflow_count < min_overflow:
        return

    leading2, kept, overflow = trim_to_last_k_turns(messages, keep_last_turns=keep_k)
    if not overflow:
        return

    prev_summary = ""
    other_leading: list[Any] = []
    for m in leading2:
        if is_memory_summary(m):
            prev_summary = extract_summary_text(m)
        else:
            other_leading.append(m)

    log_info_event(
        logger,
        "memory_compress_start",
        thread_id=thread_id,
        total_turns=total_turns,
        overflow_turns=overflow_count,
        keep_turns=keep_k,
        has_prev_summary=bool(prev_summary),
    )

    try:
        new_summary = summarize_overflow(overflow, previous_summary=prev_summary)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "memory_compress_summarize_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return

    if not (new_summary or "").strip():
        log_warning_event(
            logger,
            "memory_compress_summary_empty",
            thread_id=thread_id,
        )
        return

    # 重写 state.messages：
    # 1) 用 RemoveMessage 把所有现存消息按 id 清掉（含旧摘要，避免叠加）
    # 2) 追加：other_leading（保留普通 SystemMessage） + 新摘要 + kept（最近 K 个 turn）
    removes: list[Any] = []
    for m in messages:
        mid = getattr(m, "id", None)
        if mid:
            removes.append(RemoveMessage(id=mid))

    summary_msg = build_summary_system_message(new_summary)
    new_msgs: list[Any] = []
    new_msgs.extend(other_leading)
    new_msgs.append(summary_msg)
    new_msgs.extend(kept)

    try:
        agent.update_state(config, {"messages": removes + new_msgs})
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
        kept_messages=len(kept),
        summary_chars=len(new_summary),
    )
