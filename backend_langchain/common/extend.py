"""
通用扩展：HF 镜像默认、会话标题 fallback / LLM 润色、异步落库等。
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable

from django.db import close_old_connections
from django.db.models import Model
from langchain_core.messages import HumanMessage

from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

_DEFAULT_MIRROR = "https://hf-mirror.com"
_TITLE_MAX_LEN = 30


def fallback_chat_title(message: str) -> str:
    """新会话占位标题：取用户首条消息前 20 字；异步润色前写入库。"""
    t = (message[:20] or "新对话").strip()
    return t if t else "新对话"


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
    model: type[Model],
    thread_name_prefix: str,
    log_context: str,
) -> None:
    """主流程已用 fallback 标题落库后，在后台线程调用 polish_fn 并 update 会话 title。"""
    if not (user_message or "").strip():
        return

    def _run() -> None:
        close_old_connections()
        try:
            polished = polish_fn(user_message)
            title = (polished or "")[:255]
            model.objects.filter(pk=conversation_id, user_id=user_id).update(title=title)
        except Exception:
            logger.exception(
                "async polish title failed (%s) conv_id=%s user_id=%s",
                log_context,
                conversation_id,
                user_id,
            )
        finally:
            close_old_connections()

    threading.Thread(
        target=_run,
        name=f"{thread_name_prefix}-{conversation_id}",
        daemon=True,
    ).start()
