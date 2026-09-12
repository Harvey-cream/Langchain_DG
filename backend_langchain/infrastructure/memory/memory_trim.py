"""
按 turn 切分 + 工具安全边界裁剪（不依赖 token，先做条数版）。

文件分区（本模块均为 Turn 域，Token 触发见 token_budget.py / memory.py）：
- 共用：摘要标记 MEMORY_SUMMARY_KEY
- Turn 切分：split_messages_into_turns / count_turns
- Turn 安全：is_turn_complete / partition_turns_by_completeness
- Turn 裁剪辅助：trim_to_last_k_turns

约定：
- 一个 turn = 从一条 HumanMessage 起，到下一条 HumanMessage 之前的所有消息（含中间 AI / Tool）。
- SystemMessage 不进 turn：开头若干条 SystemMessage 视为 leading（含「会话历史摘要」标记的那条），
  裁剪时整体保留，避免把摘要当成「旧对话」误裁。
- 工具安全：只在 turn 边界裁剪，永远不会把 `AIMessage(tool_calls)` 与对应 `ToolMessage` 拆开。
"""

from __future__ import annotations

from typing import Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

# ===========================================================================
# 共用：摘要标记（turn / token 两种触发方式裁剪后都会写回同一条摘要 SystemMessage）
# ===========================================================================

# 写入 SystemMessage.additional_kwargs 的标记，表明这是「会话历史摘要」一条特殊消息。
MEMORY_SUMMARY_KEY = "__memory_summary__"


def is_memory_summary(msg: BaseMessage) -> bool:
    """识别我们写入的「长期记忆摘要」 SystemMessage（用于读取已有摘要 / 增量合并）。"""
    if not isinstance(msg, SystemMessage):
        return False
    extra = getattr(msg, "additional_kwargs", None) or {}
    return bool(extra.get(MEMORY_SUMMARY_KEY))


# ===========================================================================
# Turn 域：按 HumanMessage 边界切分 messages → (leading_systems, turns)
# （turn 条数触发与 token 预算触发在裁剪前都依赖此结构；下刀单位始终是 turn）
# ===========================================================================

def split_messages_into_turns(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], list[list[BaseMessage]]]:
    """
    把消息切成 (leading_systems, turns)：
    - leading_systems：开头连续若干条 SystemMessage（含我们写入的摘要消息）。
    - turns：每个 turn 以 HumanMessage 起，含到下一条 HumanMessage 之前的所有非 System 消息。

    若中段出现 SystemMessage（罕见），归入当前 turn 一起保留。
    若 leading 之后第一条不是 HumanMessage（脏数据），将形成一个「无 Human 起点」的 orphan turn，
    上游不应对其单独裁剪丢弃，而应整段留给摘要逻辑处理或保留。
    """
    leading: list[BaseMessage] = []
    turns: list[list[BaseMessage]] = []
    current: list[BaseMessage] | None = None

    i = 0
    n = len(messages)
    while i < n and isinstance(messages[i], SystemMessage):
        leading.append(messages[i])
        i += 1

    while i < n:
        msg = messages[i]
        if isinstance(msg, HumanMessage):
            if current is not None:
                turns.append(current)
            current = [msg]
        else:
            if current is None:
                current = [msg]
            else:
                current.append(msg)
        i += 1

    if current is not None:
        turns.append(current)

    return leading, turns


# ===========================================================================
# Turn 域：轮次统计（供 MEMORY_MAX_TURNS 触发判定使用）
# ===========================================================================

def count_turns(messages: Sequence[BaseMessage]) -> int:
    """统计有多少个完整对话轮（不含 leading SystemMessage）。"""
    _, turns = split_messages_into_turns(messages)
    return len(turns)


# ===========================================================================
# Turn 域：完整性 / 工具链安全（未完成 turn 留在热区，永不在 turn 内部下刀）
# ===========================================================================

def is_turn_complete(turn: Sequence[BaseMessage]) -> bool:
    """一轮须以用户消息开头，以已闭合的助手/工具链结束。"""
    if not turn:
        return False
    if not any(isinstance(m, HumanMessage) for m in turn):
        return False
    if isinstance(turn[-1], HumanMessage):
        return False
    pending: set[str] = set()
    for m in turn:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls or []:
                if isinstance(tc, dict) and tc.get("id"):
                    pending.add(str(tc["id"]))
        if isinstance(m, ToolMessage) and m.tool_call_id:
            pending.discard(str(m.tool_call_id))
    return not pending


def partition_turns_by_completeness(
    turns: list[list[BaseMessage]],
) -> tuple[list[list[BaseMessage]], list[BaseMessage]]:
    """末尾未完成 turn 整体留在热区，只压缩更早的完整 turn。"""
    if not turns:
        return [], []
    if is_turn_complete(turns[-1]):
        return turns, []
    return turns[:-1], [m for m in turns[-1]]


# ===========================================================================
# Turn 域：按保留轮数 K 切 overflow / kept（独立辅助；主流程在 memory.maybe_compress_history）
# ===========================================================================

def trim_to_last_k_turns(
    messages: Sequence[BaseMessage],
    *,
    keep_last_turns: int,
) -> tuple[list[BaseMessage], list[BaseMessage], list[BaseMessage]]:
    """
    按 turn 数裁剪：
    - 返回 (leading_systems, kept_messages, overflow_messages)
    - leading_systems：开头的 SystemMessage（含摘要），整体保留
    - kept_messages：最后 keep_last_turns 个完整 turn 拼起来的消息
    - overflow_messages：之前的 turn 拼起来的消息（送去摘要）

    保证：永远不在 turn 内部下刀（工具安全边界）。
    """
    leading, turns = split_messages_into_turns(messages)
    if keep_last_turns < 0:
        keep_last_turns = 0

    if len(turns) <= keep_last_turns:
        kept_msgs: list[BaseMessage] = []
        for t in turns:
            kept_msgs.extend(t)
        return list(leading), kept_msgs, []

    if keep_last_turns == 0:
        overflow_turns = list(turns)
        kept_turns: list[list[BaseMessage]] = []
    else:
        overflow_turns = list(turns[:-keep_last_turns])
        kept_turns = list(turns[-keep_last_turns:])

    overflow_msgs: list[BaseMessage] = []
    for t in overflow_turns:
        overflow_msgs.extend(t)

    kept_msgs2: list[BaseMessage] = []
    for t in kept_turns:
        kept_msgs2.extend(t)

    return list(leading), kept_msgs2, overflow_msgs
