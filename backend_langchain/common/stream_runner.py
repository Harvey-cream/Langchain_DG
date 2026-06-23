"""LangGraph 异步流式编排，供 SSE 直接消费。"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from typing import Literal

from langchain_core.messages import HumanMessage

from backend_langchain.logger_func import call_trace_callback
from common.agent import message_content_to_text
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


def reply_from_events(events: list[dict]) -> str:
    parts: list[str] = []
    had_interrupt = False
    for evt in events:
        t = evt.get("type")
        if t == "delta":
            parts.append(evt.get("text") or "")
        elif t == "interrupt":
            had_interrupt = True
    reply = "".join(parts).strip()
    if had_interrupt and not reply:
        return _INTERRUPT_HINT
    return reply


async def _quick_llm_events(
    *,
    prompt: str,
    temperature: float,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict]:
    llm = get_qwen_chat_model(temperature=temperature, streaming=True)
    async for chunk in llm.astream([HumanMessage(content=prompt)]):
        if cancel_event is not None and cancel_event.is_set():
            break
        piece = message_content_to_text(getattr(chunk, "content", chunk))
        if piece:
            yield {"type": "delta", "text": piece}


async def _graph_events(
    *,
    kind: AgentKind,
    prompt: str,
    thread_id: str,
    temperature: float,
    trace_cb: Callable[..., None] | None = None,
    cancel_event: asyncio.Event | None = None,
    enable_web_search: bool = False,
) -> AsyncIterator[dict]:
    stream_fn = _STREAM_FN[kind]
    stream_kw: dict = {}
    if kind == "main":
        stream_kw["enable_web_search"] = enable_web_search

    call_trace_callback(trace_cb, "stream_route", logger=logger, route="langgraph")
    call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
    try:
        for attempt in range(2):
            active_tid = thread_id if attempt == 0 else _recovery_thread_id(thread_id)
            got_output = False
            try:
                async for evt in stream_fn(
                    prompt_text=prompt,
                    thread_id=active_tid,
                    temperature=temperature,
                    cancel_event=cancel_event,
                    **stream_kw,
                ):
                    got_output = True
                    yield evt
                if got_output or attempt == 1:
                    return
            except Exception as e:  # noqa: BLE001
                if attempt == 0 and _is_missing_tool_output_error(e):
                    call_trace_callback(
                        trace_cb, "langgraph_retry_new_thread", logger=logger
                    )
                    continue
                raise
    finally:
        call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)


async def stream_chat_events(
    kind: AgentKind,
    user_input: str,
    *,
    thread_id: str,
    temperature: float = 0.45,
    trace_cb: Callable[..., None] | None = None,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict]:
    stream_fn = _STREAM_FN[kind]
    stream_kw: dict = {}
    if kind == "main":
        stream_kw["enable_web_search"] = enable_web_search

    if resume_pdf is not None:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="resume_pdf")
        call_trace_callback(trace_cb, "agent_invoke_enter", logger=logger)
        try:
            async for evt in stream_fn(
                thread_id=thread_id,
                temperature=temperature,
                resume_pdf=resume_pdf,
                cancel_event=cancel_event,
                **stream_kw,
            ):
                yield evt
        finally:
            call_trace_callback(trace_cb, "agent_invoke_exit", logger=logger)
        return

    if not (user_input or "").strip():
        raise ValueError("user_input is empty")

    quick = _QUICK[kind](user_input)
    if quick:
        call_trace_callback(trace_cb, "stream_route", logger=logger, route="quick_llm")
        async for evt in _quick_llm_events(
            prompt=quick, temperature=temperature, cancel_event=cancel_event
        ):
            yield evt
        return

    prompt = _WRAP[kind](user_input, skill_context=_SKILL[kind](user_input))
    async for evt in _graph_events(
        kind=kind,
        prompt=prompt,
        thread_id=thread_id,
        temperature=temperature,
        trace_cb=trace_cb,
        cancel_event=cancel_event,
        enable_web_search=enable_web_search,
    ):
        yield evt
