"""LangGraph 流式事件写入 queue，供 Django SSE 消费。"""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue
from typing import Callable, Iterator, Literal, Optional

from langchain_core.messages import HumanMessage

from backend_langchain.logger_func import call_trace_callback
from common.agent import _message_content_to_text
from common.extend import quick_agent_greeting_prompt, quick_interview_greeting_prompt
from common.skill_router import build_agent_skill_context, build_interview_skill_context
from config.config import get_qwen_chat_model
from Langchain_Agent.agents import stream_agent, stream_interview_agent
from Langchain_Agent.prompts import wrap_agent_user_message, wrap_interview_user_message

logger = logging.getLogger(__name__)

AgentKind = Literal["main", "interview"]
_INTERRUPT_HINT = "（请在界面点击按钮确认或取消 PDF 导出。）"

_STREAM_FN = {"main": stream_agent, "interview": stream_interview_agent}
_WRAP = {"main": wrap_agent_user_message, "interview": wrap_interview_user_message}
_SKILL = {"main": build_agent_skill_context, "interview": build_interview_skill_context}
_QUICK = {"main": quick_agent_greeting_prompt, "interview": quick_interview_greeting_prompt}


def _is_missing_tool_output_error(exc: BaseException) -> bool:
    return "No tool output found for function call" in str(exc)


def _recovery_thread_id(thread_id: str) -> str:
    return f"{thread_id}:recover:{int(time.time() * 1000)}"


def _quick_llm_stream(
    token_queue: Queue,
    *,
    prompt: str,
    temperature: float,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    llm = get_qwen_chat_model(temperature=temperature, streaming=True)
    parts: list[str] = []
    for chunk in llm.stream([HumanMessage(content=prompt)]):
        if cancel_event is not None and cancel_event.is_set():
            break
        piece = _message_content_to_text(getattr(chunk, "content", chunk))
        if piece:
            parts.append(piece)
            token_queue.put({"type": "delta", "text": piece})
    return "".join(parts).strip()


def _collect_stream(
    events: Iterator[dict],
    token_queue: Queue,
    *,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    parts: list[str] = []
    had_interrupt = False
    for evt in events:
        if cancel_event is not None and cancel_event.is_set():
            break
        token_queue.put(evt)
        t = evt.get("type")
        if t == "delta":
            parts.append(evt.get("text") or "")
        elif t == "interrupt":
            had_interrupt = True
    reply = "".join(parts).strip()
    if had_interrupt and not reply:
        return _INTERRUPT_HINT
    return reply


def _run_graph_stream(
    token_queue: Queue,
    *,
    kind: AgentKind,
    prompt: str,
    thread_id: str,
    temperature: float,
    trace_cb: Optional[Callable[..., None]] = None,
    cancel_event: Optional[threading.Event] = None,
    enable_web_search: bool = False,
) -> str:
    stream_fn = _STREAM_FN[kind]
    stream_kw: dict = {}
    if kind == "main":
        stream_kw["enable_web_search"] = enable_web_search

    call_trace_callback(trace_cb, "stream_route", logger=logger, route="langgraph")
    call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
    try:
        for attempt in range(2):
            active_tid = thread_id if attempt == 0 else _recovery_thread_id(thread_id)
            try:
                events = stream_fn(
                    prompt_text=prompt,
                    thread_id=active_tid,
                    temperature=temperature,
                    cancel_event=cancel_event,
                    **stream_kw,
                )
                reply = _collect_stream(events, token_queue, cancel_event=cancel_event)
                if reply or attempt == 1:
                    return reply
            except Exception as e:  # noqa: BLE001
                if attempt == 0 and _is_missing_tool_output_error(e):
                    call_trace_callback(
                        trace_cb, "langgraph_retry_new_thread", logger=logger
                    )
                    continue
                raise
        return ""
    finally:
        call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)


def run_stream_with_queue(
    kind: AgentKind,
    user_input: str,
    token_queue: Queue,
    *,
    thread_id: str,
    temperature: float = 0.45,
    trace_cb: Optional[Callable[..., None]] = None,
    resume_pdf: Optional[bool] = None,
    enable_web_search: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    stream_fn = _STREAM_FN[kind]
    stream_kw: dict = {}
    if kind == "main":
        stream_kw["enable_web_search"] = enable_web_search

    if resume_pdf is not None:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="resume_pdf")
        call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
        try:
            return _collect_stream(
                stream_fn(
                    thread_id=thread_id,
                    temperature=temperature,
                    resume_pdf=resume_pdf,
                    cancel_event=cancel_event,
                    **stream_kw,
                ),
                token_queue,
                cancel_event=cancel_event,
            )
        finally:
            call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    quick = _QUICK[kind](user_input)
    if quick:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="quick_llm")
        return _quick_llm_stream(
            token_queue, prompt=quick, temperature=temperature, cancel_event=cancel_event
        )

    prompt = _WRAP[kind](user_input, skill_context=_SKILL[kind](user_input))
    return _run_graph_stream(
        token_queue,
        kind=kind,
        prompt=prompt,
        thread_id=thread_id,
        temperature=temperature,
        trace_cb=trace_cb,
        cancel_event=cancel_event,
        enable_web_search=enable_web_search,
    )


def run_chat_stream_with_queue(
    user_input: str,
    token_queue: Queue,
    **kwargs: object,
) -> str:
    return run_stream_with_queue("main", user_input, token_queue, **kwargs)


def run_interview_chat_stream_with_queue(
    user_input: str,
    token_queue: Queue,
    **kwargs: object,
) -> str:
    return run_stream_with_queue("interview", user_input, token_queue, **kwargs)
