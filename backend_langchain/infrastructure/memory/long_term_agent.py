"""长期记忆：读侧注入 + 异步调度 Memory Agent 图。

写路径图见 `infrastructure.memory.agent`（trigger → extract → apply）。
"""
from __future__ import annotations

import asyncio
import logging
import os

from infrastructure.memory.long_term_store import get_long_term_store
from infrastructure.memory.long_term_trigger import memory_agent_enabled
from backend_langchain.logger_func import log_exception_event

logger = logging.getLogger(__name__)

_graph = None


def _retrieve_top_k() -> int:
    try:
        return max(1, min(10, int(os.getenv("MEMORY_RETRIEVE_TOP_K", "5") or "5")))
    except ValueError:
        return 5


def _retrieve_max_chars() -> int:
    try:
        return max(200, int(os.getenv("MEMORY_RETRIEVE_MAX_CHARS", "1200") or "1200"))
    except ValueError:
        return 1200


def _get_graph():
    global _graph
    if _graph is None:
        from infrastructure.memory.agent import build_memory_agent_graph

        _graph = build_memory_agent_graph()
    return _graph


def format_retrieved_memories(user_id: int, query: str) -> str:
    """同步：检索并格式化为可注入的 System 文本；无结果返回空串。"""
    if not memory_agent_enabled():
        return ""
    q = (query or "").strip()
    if not q or user_id <= 0:
        return ""
    from infrastructure.memory.long_term_trigger import should_retrieve_memory

    if not should_retrieve_memory(q):
        return ""
    try:
        rows = get_long_term_store().search(q, user_id=user_id, k=_retrieve_top_k())
    except Exception:  # noqa: BLE001
        log_exception_event(logger, "long_term_retrieve_failed", user_id=user_id)
        return ""
    if not rows:
        return ""
    ranked = sorted(
        rows,
        key=lambda r: (r.distance if r.distance is not None else 1.0) - 0.15 * r.importance,
    )
    lines: list[str] = []
    total = 0
    for r in ranked:
        line = f"- [{r.memory_type}] {r.content}"
        if total + len(line) + 1 > _retrieve_max_chars():
            break
        lines.append(line)
        total += len(line) + 1
    if not lines:
        return ""
    return "【长期记忆（跨会话，请遵守其中稳定偏好/约束）】\n" + "\n".join(lines)


def schedule_long_term_memory(
    *,
    user_id: int,
    user_text: str,
    assistant_text: str,
) -> None:
    if not memory_agent_enabled():
        return
    if user_id <= 0:
        return

    async def _run() -> None:
        try:
            await _get_graph().ainvoke(
                {
                    "user_id": user_id,
                    "user_text": user_text or "",
                    "assistant_text": assistant_text or "",
                }
            )
        except Exception:  # noqa: BLE001
            log_exception_event(logger, "long_term_memory_agent_failed", user_id=user_id)

    asyncio.create_task(_run())
