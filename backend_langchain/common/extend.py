"""
通用扩展：HF 镜像默认、会话标题 fallback / LLM 润色、异步落库等。
"""
from __future__ import annotations

import asyncio
import logging
import os
from difflib import SequenceMatcher
from typing import Any, Callable

from langchain_core.messages import HumanMessage
from sqlalchemy import update

from backend_langchain.logger_func import log_exception_event
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

_DEFAULT_MIRROR = "https://hf-mirror.com"
_TITLE_MAX_LEN = 30
_GREETING_QUICK_REPLIES = {
    "在吗": "在吗",
    "在不在": "在不在",
    "有人吗": "有人吗",
    "在嘛": "在嘛",
    "在么": "在么",
    "你好": "你好",
    "您好": "您好",
    "嗨": "嗨",
    "哈喽": "哈喽",
    "哈啰": "哈啰",
    "早上好": "早上好",
    "中午好": "中午好",
    "下午好": "下午好",
    "晚上好": "晚上好",
    "hi": "hi",
    "hey": "hey",
    "yo": "yo",
    "hello": "hello",
    "good morning": "good morning",
    "good afternoon": "good afternoon",
    "good evening": "good evening",
}
_CAPABILITY_QUICK_INPUTS = {
    "你能做什么",
    "你会什么",
    "你会做什么",
    "你可以做什么",
    "你可以帮我做什么",
    "你能帮我做什么",
    "你可以帮我什么",
    "你能帮我什么",
    "你有什么功能",
    "你有哪些功能",
    "你都能干啥",
    "你都能做啥",
    "你可以帮我干啥",
    "你能帮我干啥",
    "what can you do",
}
_QUICK_ROUTE_FUZZY_CANDIDATES = tuple(_GREETING_QUICK_REPLIES.keys()) + tuple(
    _CAPABILITY_QUICK_INPUTS
)
_FUZZY_MIN_SIM = 0.78


def fallback_chat_title(message: str) -> str:
    """新会话占位标题：取用户首条消息前 20 字；异步润色前写入库。"""
    t = (message[:20] or "新对话").strip()
    return t if t else "新对话"


def _quick_greeting_hit(message: str) -> str | None:
    text = (message or "").strip().lower()
    if not text:
        return None
    normalized = text.strip("。！？!?，,~～ ")
    if len(normalized) > 20:
        return None
    if normalized in _CAPABILITY_QUICK_INPUTS:
        return normalized
    exact = _GREETING_QUICK_REPLIES.get(normalized)
    if exact:
        return exact

    # 轻量模糊匹配：仅在短句场景启用，避免关键词稍有变体就 miss。
    best_text: str | None = None
    best_score = 0.0
    for cand in _QUICK_ROUTE_FUZZY_CANDIDATES:
        score = SequenceMatcher(None, normalized, cand).ratio()
        if score > best_score:
            best_score = score
            best_text = cand
    if best_text and best_score >= _FUZZY_MIN_SIM:
        return normalized
    return None


def quick_agent_greeting_prompt(message: str) -> str | None:
    """企业知识库AI助手：问候/短句快速路径提示词（不走 ReAct）。"""
    hit = _quick_greeting_hit(message)
    if not hit:
        return None
    return (
        "你是「企业知识库AI助手」。用户刚发来一条问候，请直接自然回复。\n"
        "要求：\n"
        "1) 先简短接住问候（1 句）；\n"
        "2) 再用 1-2 句说明你能做什么（上传文档后的检索问答、摘要、制度/资料速查）；\n"
        "3) 末尾给一个自然引导，鼓励用户上传文档或直接问文档相关问题；\n"
        "4) 不要使用 ReAct 结构，不要输出 Thought/Action/Observation/Final Answer；\n"
        "5) 每次表达尽量有变化，口语化，控制在 80 字以内。\n\n"
        f"用户消息：{hit}"
    )


def quick_interview_greeting_prompt(message: str) -> str | None:
    """AI 面试助手：问候/短句快速路径提示词（不走 ReAct）。"""
    hit = _quick_greeting_hit(message)
    if not hit:
        return None
    return (
        "你是温暖、专业的 AI 面试助手。用户刚发来一条问候，请直接自然回复。\n"
        "要求：\n"
        "1) 先简短接住问候（1 句）；\n"
        "2) 再用 1-2 句告诉用户你能做什么（重点：面试题讲解、模拟面试追问、答题优化、学习路线）；\n"
        "3) 末尾给一个自然的引导句，鼓励用户直接发岗位/题目/答案让你优化；\n"
        "4) 不要使用 ReAct 结构，不要输出 Thought/Action/Observation/Final Answer；\n"
        "5) 每次表达尽量有变化，口语化，控制在 80 字以内。\n\n"
        f"用户消息：{hit}"
    )


def _normalize_llm_title_line(resp: Any, *, fallback: str) -> str:
    text = (getattr(resp, "content", None) or str(resp)).strip()
    text = text.splitlines()[0].strip()
    for q in ('"', "'", "「", "」", "《", "》"):
        text = text.replace(q, "")
    text = text.strip()
    if len(text) > _TITLE_MAX_LEN:
        text = text[:_TITLE_MAX_LEN]
    return text if text else fallback


def polish_agent_conversation_title(user_message: str) -> str:
    """普通 Agent 会话：千问根据首条消息生成简短标题。"""
    fb = fallback_chat_title(user_message)
    if not user_message.strip():
        return "新对话"
    try:
        llm = get_qwen_chat_model(temperature=0.3)
        prompt = (
            "你是标题助手。根据用户的第一条消息，生成一个简短、通顺的中文会话标题。"
            f"要求：5～15 个字为宜，不超过 {_TITLE_MAX_LEN} 个字；不要引号、不要标点结尾、不要解释、只输出标题一行。\n\n"
            f"用户消息：\n{user_message[:800]}"
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        return _normalize_llm_title_line(resp, fallback=fb)
    except Exception:
        return fb


def polish_interview_title(user_message: str) -> str:
    """面试会话：提示词侧重求职/面试场景。"""
    fb = fallback_chat_title(user_message)
    if not user_message.strip():
        return "新对话"
    try:
        llm = get_qwen_chat_model(temperature=0.3)
        prompt = (
            "你是标题助手。根据用户关于面试/求职的第一条消息，生成一个简短、通顺的中文会话标题。"
            f"要求：5～15 个字为宜，不超过 {_TITLE_MAX_LEN} 个字；不要引号、不要标点结尾、不要解释、只输出标题一行。\n\n"
            f"用户消息：\n{user_message[:800]}"
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        return _normalize_llm_title_line(resp, fallback=fb)
    except Exception:
        return fb


def apply_hf_mirror_default() -> None:
    """
    Hugging Face Hub 国内镜像：huggingface_hub / sentence_transformers 会读 HF_ENDPOINT。
    未设置时默认 https://hf-mirror.com；若需官方源可设 HF_ENDPOINT=https://huggingface.co。
    在首次下载/加载 HF 模型前调用；已设置 HF_ENDPOINT 时不修改。
    """
    os.environ.setdefault("HF_ENDPOINT", _DEFAULT_MIRROR)


def schedule_async_title_polish(
    *,
    conversation_id: int,
    user_id: int,
    user_message: str,
    polish_fn: Callable[[str], str],
    table: Any,
    log_context: str,
) -> None:
    """主流程已用 fallback 标题落库后，后台润色并 update 会话 title。"""
    if not (user_message or "").strip():
        return

    async def _run() -> None:
        from app.db import SessionLocal

        try:
            polished = polish_fn(user_message)
            title = (polished or "")[:255]
            async with SessionLocal() as session:
                await session.execute(
                    update(table)
                    .where(table.id == conversation_id, table.user_id == user_id)
                    .values(title=title)
                )
                await session.commit()
        except Exception:
            log_exception_event(
                logger,
                "async_polish_title_failed",
                log_context=log_context,
                conversation_id=conversation_id,
                user_id=user_id,
            )

    asyncio.create_task(_run())
