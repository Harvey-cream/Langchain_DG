"""方案 B：两个独立 LangGraph 图（超级智能体 + 面试大师），共用 build_agent_graph。

差异只有两处：工具集 与 system_prompt。其余构图、流式、checkpoint 完全一致。
图按需懒加载并缓存；主对话因联网开关需要不同工具集，故缓存本地 / 联网两张。
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from common.agent import build_agent_graph, stream_graph_chat_model_events
from Langchain_Agent.prompts import AGENT_SYSTEM_PREFIX, INTERVIEW_SYSTEM_PREFIX
from Langchain_Agent.tools import get_all_agent_tools
from Langchain_Agent.tools.interview_rag import INTERVIEW_RAG_TOOLS

_main_local: CompiledStateGraph | None = None
_main_web: CompiledStateGraph | None = None
_interview: CompiledStateGraph | None = None


def get_stream_agent_executor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """超级智能体图：RAG + PDF + MCP 工具（enable_web_search 决定是否含联网搜索）。"""
    global _main_local, _main_web
    if enable_web_search:
        if _main_web is None:
            _main_web = build_agent_graph(
                tools=get_all_agent_tools(enable_web_search=True),
                system_prompt=AGENT_SYSTEM_PREFIX,
                temperature=temperature,
                streaming=True,
            )
        return _main_web
    if _main_local is None:
        _main_local = build_agent_graph(
            tools=get_all_agent_tools(enable_web_search=False),
            system_prompt=AGENT_SYSTEM_PREFIX,
            temperature=temperature,
            streaming=True,
        )
    return _main_local


def get_stream_interview_executor(*, temperature: float = 0.45) -> CompiledStateGraph:
    """面试大师图：仅面试题库 RAG + PDF 工具，不挂 MCP。"""
    global _interview
    if _interview is None:
        _interview = build_agent_graph(
            tools=INTERVIEW_RAG_TOOLS,
            system_prompt=INTERVIEW_SYSTEM_PREFIX,
            temperature=temperature,
            streaming=True,
        )
    return _interview


async def stream_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_stream_agent_executor(temperature=temperature, enable_web_search=enable_web_search)
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        cancel_event=cancel_event,
    ):
        yield evt


async def stream_interview_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_stream_interview_executor(temperature=temperature)
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        cancel_event=cancel_event,
    ):
        yield evt
