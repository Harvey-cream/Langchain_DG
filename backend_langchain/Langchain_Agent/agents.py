"""两个独立 LangGraph Agent：超级智能体 + 面试大师。"""

from __future__ import annotations

import threading
from typing import Any, Iterator, Optional

from langgraph.graph.state import CompiledStateGraph

from common.agent import build_react_rag_agent, stream_graph_chat_model_events
from Langchain_Agent.tools import get_all_agent_tools
from Langchain_Agent.tools.interview_rag import INTERVIEW_RAG_TOOLS

_agent_stream_local: CompiledStateGraph | None = None
_agent_stream_web: CompiledStateGraph | None = None
_interview_stream_cache: CompiledStateGraph | None = None


def get_stream_agent_executor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    global _agent_stream_local, _agent_stream_web
    target = _agent_stream_web if enable_web_search else _agent_stream_local
    if target is None:
        tools = list(get_all_agent_tools(enable_web_search=enable_web_search))
        target = build_react_rag_agent(temperature=temperature, streaming=True, tools=tools)
        if enable_web_search:
            _agent_stream_web = target
        else:
            _agent_stream_local = target
    return target


def stream_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    agent = get_stream_agent_executor(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )
    yield from stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        cancel_event=cancel_event,
    )


def get_stream_interview_executor(*, temperature: float = 0.45) -> CompiledStateGraph:
    global _interview_stream_cache
    if _interview_stream_cache is None:
        _interview_stream_cache = build_react_rag_agent(
            tools=list(INTERVIEW_RAG_TOOLS), temperature=temperature, streaming=True
        )
    return _interview_stream_cache


def stream_interview_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    agent = get_stream_interview_executor(temperature=temperature)
    yield from stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        cancel_event=cancel_event,
    )
