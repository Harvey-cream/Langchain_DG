from __future__ import annotations

import os
from typing import Iterable

from User.models import User, UserConversation, UserSession


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _truncate(text: str, max_chars: int) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip() + "…"


def _format_turns(turns: Iterable[UserSession], *, max_q_chars: int, max_a_chars: int) -> str:
    lines: list[str] = []
    for idx, item in enumerate(turns, start=1):
        q = _truncate(item.question, max_q_chars)
        a = _truncate(item.ai_response, max_a_chars)
        lines.append(f"第{idx}轮用户：{q}")
        lines.append(f"第{idx}轮助手：{a}")
    return "\n".join(lines).strip()


def build_agent_memory_context(
    *,
    user: User,
    conversation: UserConversation | None,
) -> str:
    """
    构建普通 Agent 的窗口记忆：
    - 同一 conversation 最近 N 轮
    - 问答分别截断，控制上下文开销
    """
    if conversation is None:
        return ""

    max_turns = _int_env("AGENT_MEMORY_TURNS", 6, minimum=1, maximum=20)
    max_q_chars = _int_env("AGENT_MEMORY_Q_MAX_CHARS", 280, minimum=80, maximum=1200)
    max_a_chars = _int_env("AGENT_MEMORY_A_MAX_CHARS", 420, minimum=120, maximum=2000)

    recent = list(
        UserSession.objects.filter(user=user, conversation=conversation)
        .order_by("-created_at")[:max_turns]
    )
    if not recent:
        return ""

    recent.reverse()
    turns = _format_turns(recent, max_q_chars=max_q_chars, max_a_chars=max_a_chars)
    if not turns:
        return ""

    return (
        "【会话记忆（最近若干轮，仅供内部参考）】\n"
        f"{turns}\n\n"
        "请在回答中保持与上述上下文一致，避免重复追问已确认的信息。"
    )

