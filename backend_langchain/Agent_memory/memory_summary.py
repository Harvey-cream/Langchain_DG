"""
长期记忆摘要：用与主 Agent 同一份 LLM（见 config.config.get_qwen_chat_model）
对溢出的 overflow 消息做 rolling 合并，输出新的会话摘要文本。

仅负责「文本合成」与「构造 SystemMessage」；不直接改 LangGraph state。
"""

from __future__ import annotations

import logging
from typing import Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from Agent_memory.memory_trim import MEMORY_SUMMARY_KEY
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)


# ===========================================================================
# 共用：摘要合成（turn 触发 / token 触发裁剪出 overflow 后，走同一条 LLM 合并路径）
# ===========================================================================

SUMMARY_PROMPT = """你是一个会话压缩助手。请把下面【历史对话片段】合并到【已有摘要】中，输出一份新的整体摘要。

要求：
- 严格基于事实，不要编造、不要推测。
- 用中文，控制在 600 字以内，越简短越好。
- 保留：用户目标、已确认事实、关键决定与约束、未解决问题、用户偏好。
- 不保留：寒暄、与目标无关的客套；工具调用过程细节仅保留有用的最终结论。
- 不要使用 Markdown 标题，仅用纯文本分行。
- 仅输出新摘要正文本身，不要加「以下是摘要：」之类的前后缀。
"""

# 单条消息进入摘要前的字数硬上限，避免输入过长。
_PER_MESSAGE_CHAR_LIMIT = 1500


def _format_messages_for_summary(messages: Sequence[BaseMessage]) -> str:
    """把消息列表渲染成纯文本，供小模型阅读。"""
    lines: list[str] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "用户"
        elif isinstance(m, AIMessage):
            role = "助手"
        elif isinstance(m, ToolMessage):
            role = f"工具[{getattr(m, 'name', '') or ''}]"
        elif isinstance(m, SystemMessage):
            role = "系统"
        else:
            role = m.__class__.__name__

        content = m.content if isinstance(m.content, str) else str(m.content)
        text = (content or "").strip()
        if not text:
            continue
        if len(text) > _PER_MESSAGE_CHAR_LIMIT:
            text = text[:_PER_MESSAGE_CHAR_LIMIT] + "…"
        lines.append(f"【{role}】{text}")
    return "\n".join(lines)


def build_summary_system_message(summary_text: str) -> SystemMessage:
    """构造长期记忆摘要 SystemMessage（带特殊标记，便于后续识别替换）。"""
    body = (summary_text or "").strip()
    return SystemMessage(
        content=f"【会话历史摘要（仅供模型参考，请勿原样复述）】\n{body}",
        additional_kwargs={MEMORY_SUMMARY_KEY: True},
    )


def extract_summary_text(msg: BaseMessage) -> str:
    """从我们写入的摘要 SystemMessage 中提取纯摘要正文（去掉前缀提示）。"""
    if not isinstance(msg, SystemMessage):
        return ""
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    text = (content or "").strip()
    if "\n" in text:
        # 第一行是「【会话历史摘要…】」前缀，去掉
        return text.split("\n", 1)[1].strip()
    return text


def summarize_overflow(
    overflow_messages: Sequence[BaseMessage],
    *,
    previous_summary: str = "",
    temperature: float = 0.2,
) -> str:
    """
    用同一 LLM 把 overflow_messages 与已有 previous_summary 合并为新摘要。

    返回：新摘要纯文本（不含 SystemMessage 包装）。
    异常时由调用方 catch（推荐：失败则放弃本次压缩，保留原 messages）。
    """
    if not overflow_messages:
        return (previous_summary or "").strip()

    overflow_text = _format_messages_for_summary(overflow_messages)
    if not overflow_text.strip():
        return (previous_summary or "").strip()

    user_payload_parts: list[str] = []
    if (previous_summary or "").strip():
        user_payload_parts.append(f"【已有摘要】\n{previous_summary.strip()}")
    user_payload_parts.append(f"【历史对话片段（按时间顺序）】\n{overflow_text}")
    user_payload = "\n\n".join(user_payload_parts)

    llm = get_qwen_chat_model(temperature=temperature, streaming=False)
    resp = llm.invoke(
        [
            SystemMessage(content=SUMMARY_PROMPT),
            HumanMessage(content=user_payload),
        ]
    )
    raw = getattr(resp, "content", resp)
    if isinstance(raw, list):
        parts: list[str] = []
        for p in raw:
            if isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
            elif isinstance(p, str):
                parts.append(p)
        text = "".join(parts)
    else:
        text = str(raw or "")
    return text.strip()
