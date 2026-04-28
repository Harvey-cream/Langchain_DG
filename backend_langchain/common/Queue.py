"""Django SSE 用：把 LangGraph 事件与问候快路径写入 queue，不负责构图逻辑。"""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue
from typing import Callable, Optional

from langchain_core.messages import HumanMessage

from config.config import get_qwen_chat_model
from Langchain_Agent.main_agent import stream_agent
from Langchain_Agent.utils.answer_format_prompt import wrap_inline_tool_user_message
from Langchain_Agent1.interview_agent import stream_interview_agent
from backend_langchain.logger_func import call_trace_callback
from common.agent import _message_content_to_text
from common.extend import quick_agent_greeting_prompt, quick_interview_greeting_prompt
from common.skill_router import build_agent_skill_context, build_interview_skill_context

logger = logging.getLogger(__name__)


def _is_missing_tool_output_error(exc: BaseException) -> bool:
    return "No tool output found for function call" in str(exc)


def _recovery_thread_id(thread_id: str) -> str:
    return f"{thread_id}:recover:{int(time.time() * 1000)}"


def _quick_llm_stream_to_queue(
    token_queue: Queue,
    *,
    prompt: str,
    temperature: float,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    llm = get_qwen_chat_model(temperature=temperature, streaming=True)
    acc: list[str] = []
    for chunk in llm.stream([HumanMessage(content=prompt)]):
        if cancel_event is not None and cancel_event.is_set():
            break
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
    resume_pdf: Optional[bool] = None,
    enable_web_search: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    """流式对话：token_queue 中放入 delta|status|interrupt；resume_pdf 走 Command.resume，跳过快路径。"""
    if resume_pdf is not None:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="resume_pdf")
        call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
        try:
            parts: list[str] = []
            for evt in stream_agent(
                thread_id=thread_id,
                temperature=temperature,
                resume_pdf=resume_pdf,
                enable_web_search=enable_web_search,
                cancel_event=cancel_event,
            ):
                token_queue.put(evt)
                if evt.get("type") == "delta":
                    parts.append(evt.get("text") or "")
            return "".join(parts).strip()
        finally:
            call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)

    quick_prompt = quick_agent_greeting_prompt(user_input)
    if quick_prompt:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="quick_llm")
        return _quick_llm_stream_to_queue(
            token_queue,
            prompt=quick_prompt,
            temperature=temperature,
            cancel_event=cancel_event,
        )

    call_trace_callback(trace_cb, "stream_route", logger=logger, route="langgraph")
    call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
    try:
        skill_context = build_agent_skill_context(user_input)
        prompt = wrap_inline_tool_user_message(
            user_input,
            memory_context=memory_context,
            skill_context=skill_context,
        )
        for attempt in range(2):
            parts: list[str] = []
            had_interrupt = False
            active_thread_id = thread_id if attempt == 0 else _recovery_thread_id(thread_id)
            try:
                for evt in stream_agent(
                    prompt_text=prompt,
                    thread_id=active_thread_id,
                    temperature=temperature,
                    enable_web_search=enable_web_search,
                    cancel_event=cancel_event,
                ):
                    token_queue.put(evt)
                    if evt.get("type") == "delta":
                        parts.append(evt.get("text") or "")
                    elif evt.get("type") == "interrupt":
                        had_interrupt = True
                reply = "".join(parts).strip()
                if had_interrupt and not reply:
                    reply = "（请在界面点击按钮确认或取消 PDF 导出。）"
                return reply
            except Exception as e:  # noqa: BLE001
                if attempt == 0 and not parts and _is_missing_tool_output_error(e):
                    call_trace_callback(
                        trace_cb,
                        "langgraph_retry_new_thread_after_missing_tool_output",
                        logger=logger,
                    )
                    continue
                raise
    finally:
        call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)


def run_interview_chat_stream_with_queue(
    user_input: str,
    token_queue: Queue,
    *,
    thread_id: str,
    memory_context: str = "",
    temperature: float = 0.45,
    trace_cb: Optional[Callable[..., None]] = None,
    resume_pdf: Optional[bool] = None,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    """面试流式：队列事件同 run_chat_stream_with_queue。"""
    from Langchain_Agent1.utils.prompt import wrap_interview_user_message

    if resume_pdf is not None:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="resume_pdf")
        call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
        try:
            parts: list[str] = []
            for evt in stream_interview_agent(
                thread_id=thread_id,
                temperature=temperature,
                resume_pdf=resume_pdf,
                cancel_event=cancel_event,
            ):
                token_queue.put(evt)
                if evt.get("type") == "delta":
                    parts.append(evt.get("text") or "")
            return "".join(parts).strip()
        finally:
            call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    quick_prompt = quick_interview_greeting_prompt(user_input)
    if quick_prompt:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="quick_llm")
        return _quick_llm_stream_to_queue(
            token_queue,
            prompt=quick_prompt,
            temperature=temperature,
            cancel_event=cancel_event,
        )

    call_trace_callback(trace_cb, "stream_route", logger=logger, route="langgraph")
    call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
    try:
        skill_context = build_interview_skill_context(user_input)
        prompt = wrap_interview_user_message(
            user_input,
            memory_context=memory_context,
            skill_context=skill_context,
        )
        for attempt in range(2):
            parts: list[str] = []
            had_interrupt = False
            active_thread_id = thread_id if attempt == 0 else _recovery_thread_id(thread_id)
            try:
                for evt in stream_interview_agent(
                    prompt_text=prompt,
                    thread_id=active_thread_id,
                    temperature=temperature,
                    cancel_event=cancel_event,
                ):
                    token_queue.put(evt)
                    if evt.get("type") == "delta":
                        parts.append(evt.get("text") or "")
                    elif evt.get("type") == "interrupt":
                        had_interrupt = True
                reply = "".join(parts).strip()
                if had_interrupt and not reply:
                    reply = "（请在界面点击按钮确认或取消 PDF 导出。）"
                return reply
            except Exception as e:  # noqa: BLE001
                if attempt == 0 and not parts and _is_missing_tool_output_error(e):
                    call_trace_callback(
                        trace_cb,
                        "langgraph_retry_new_thread_after_missing_tool_output",
                        logger=logger,
                    )
                    continue
                raise
    finally:
        call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)