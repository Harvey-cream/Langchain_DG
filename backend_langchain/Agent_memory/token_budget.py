"""消息 token 粗估（字符/4），用于触发压缩，不在 turn 中间下刀。"""
from __future__ import annotations

from langchain_core.messages import BaseMessage

# ===========================================================================
# Token 域：估算 checkpoint messages 总 token，供 MEMORY_TOKEN_BUDGET 触发判定
# （仅负责「是否该压」与日志；实际裁剪仍按 turn 边界，见 memory_trim）
# ===========================================================================


def estimate_text_tokens(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    return max(1, len(t) // 4)


def estimate_message_tokens(msg: BaseMessage) -> int:
    content = getattr(msg, "content", None)
    if content is None:
        return 0
    if isinstance(content, str):
        return estimate_text_tokens(content)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return estimate_text_tokens("".join(parts))
    return estimate_text_tokens(str(content))


def estimate_messages_tokens(messages: list[BaseMessage]) -> int:
    return sum(estimate_message_tokens(m) for m in messages)
