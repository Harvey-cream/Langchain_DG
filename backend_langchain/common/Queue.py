"""Django SSE 用：把 LangGraph 事件与问候快路径写入 queue，不负责构图逻辑。"""

from __future__ import annotations

import logging
from queue import Queue
from typing import Callable, Optional

from langchain_core.messages import HumanMessage

from config.config import get_qwen_chat_model
from Langchain_Agent.main_agent import stream_agent
from Langchain_Agent.utils.answer_format_prompt import wrap_inline_tool_user_message
from Langchain_Agent1.interview_agent import stream_interview_agent
from common.agent import _message_content_to_text
from common.extend import quick_agent_greeting_prompt, quick_interview_greeting_prompt
from common.skill_router import build_agent_skill_context, build_interview_skill_context

logger = logging.getLogger(__name__)


def _quick_llm_stream_to_queue(
    token_queue: Queue,
    *,
    prompt: str,
    temperature: float,
) -> str:
    llm = get_qwen_chat_model(temperature=temperature, streaming=True)
    acc: list[str] = []
    for chunk in llm.stream([HumanMessage(content=prompt)]):
        piece = _message_content_to_text(getattr(chunk, "content", chunk))
        if piece:
            acc.append(piece)
            token_queue.put({"type": "delta", "text": piece})
    return "".join(acc).strip()


def run_chat_stream_with_queue(
    user_input: str,
    token_queue: Queue,
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
    trace_cb: Optional[Callable[..., None]] = None,
) -> str:
    """流式对话：token_queue 中放入 {type: delta|status, text: str}，返回拼接的可见文本（用于落库兜底）。"""
    quick_prompt = quick_agent_greeting_prompt(user_input)
    if quick_prompt:
        if trace_cb:
            try:
                trace_cb("stream_route", route="quick_llm")
            except Exception:
                logger.debug("trace_cb(stream_route) failed", exc_info=True)
        return _quick_llm_stream_to_queue(
            token_queue, prompt=quick_prompt, temperature=temperature
        )

    if trace_cb:
        try:
            trace_cb("stream_route", route="langgraph")
        except Exception:
            logger.debug("trace_cb(stream_route) failed", exc_info=True)
    if trace_cb:
        try:
            trace_cb("agent_invoke_enter")
        except Exception:
            logger.debug("trace_cb(agent_invoke_enter) failed", exc_info=True)
    try:
        parts: list[str] = []
        skill_context = build_agent_skill_context(user_input)
        prompt = wrap_inline_tool_user_message(
            user_input,
            memory_context=memory_context,
            skill_context=skill_context,
        )
        for evt in stream_agent(
            prompt_text=prompt,
            thread_id=thread_id,
            temperature=temperature,
        ):
            token_queue.put(evt)
            if evt.get("type") == "delta":
                parts.append(evt.get("text") or "")
        reply = "".join(parts).strip()
    finally:
        if trace_cb:
            try:
                trace_cb("agent_invoke_exit")
            except Exception:
                logger.debug("trace_cb(agent_invoke_exit) failed", exc_info=True)
    return reply


def run_interview_chat_stream_with_queue(
    user_input: str,
    token_queue: Queue,
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
    trace_cb: Optional[Callable[..., None]] = None,
) -> str:
    """面试流式：队列事件同 run_chat_stream_with_queue。"""
    from Langchain_Agent1.utils.prompt import wrap_interview_user_message

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    quick_prompt = quick_interview_greeting_prompt(user_input)
    if quick_prompt:
        if trace_cb:
            try:
                trace_cb("stream_route", route="quick_llm")
            except Exception:
                logger.debug("trace_cb(stream_route) failed", exc_info=True)
        return _quick_llm_stream_to_queue(
            token_queue, prompt=quick_prompt, temperature=temperature
        )

    if trace_cb:
        try:
            trace_cb("stream_route", route="langgraph")
        except Exception:
            logger.debug("trace_cb(stream_route) failed", exc_info=True)
    if trace_cb:
        try:
            trace_cb("agent_invoke_enter")
        except Exception:
            logger.debug("trace_cb(agent_invoke_enter) failed", exc_info=True)
    try:
        parts: list[str] = []
        skill_context = build_interview_skill_context(user_input)
        prompt = wrap_interview_user_message(
            user_input,
            memory_context=memory_context,
            skill_context=skill_context,
        )
        for evt in stream_interview_agent(
            prompt_text=prompt,
            thread_id=thread_id,
            temperature=temperature,
        ):
            token_queue.put(evt)
            if evt.get("type") == "delta":
                parts.append(evt.get("text") or "")
        reply = "".join(parts).strip()
    finally:
        if trace_cb:
            try:
                trace_cb("agent_invoke_exit")
            except Exception:
                logger.debug("trace_cb(agent_invoke_exit) failed", exc_info=True)
    return reply