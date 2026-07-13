"""两个独立 LangGraph 图（超级智能体 + 面试大师），共用 build_agent_graph。

差异：tools、system_prompt、recall_mode。图结构：skill_recall → agent ↔ tools。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from common.agent import build_agent_graph, stream_graph_chat_model_events
from Agent_memory.memory_persist import MemoryTurnContext
from Langchain_Agent.prompts import AGENT_SYSTEM_PREFIX, INTERVIEW_SYSTEM_PREFIX
from Langchain_Agent.tools.knowledge import get_all_agent_tools, get_interview_tools

_main_local: CompiledStateGraph | None = None
_main_web: CompiledStateGraph | None = None
_interview: CompiledStateGraph | None = None


def reset_stream_agent_cache() -> None:
    """代码热重载后清图缓存，避免仍用旧节点/工具编译结果。"""
    global _main_local, _main_web, _interview
    _main_local = None
    _main_web = None
    _interview = None


def get_stream_agent_executor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """超级智能体图：Workflow RAG + MCP + PDF（enable_web_search 决定是否含联网搜索）。"""
    global _main_local, _main_web
    if enable_web_search:
        if _main_web is None:
            _main_web = build_agent_graph(
                tools=get_all_agent_tools(enable_web_search=True),
                system_prompt=AGENT_SYSTEM_PREFIX,
                recall_mode="main",
                temperature=temperature,
                streaming=True,
            )
        return _main_web
    if _main_local is None:
        _main_local = build_agent_graph(
            tools=get_all_agent_tools(enable_web_search=False),
            system_prompt=AGENT_SYSTEM_PREFIX,
            recall_mode="main",
            temperature=temperature,
            streaming=True,
        )
    return _main_local


def get_stream_interview_executor(*, temperature: float = 0.45) -> CompiledStateGraph:
    """面试大师图：Workflow RAG + PDF，不挂 MCP。"""
    global _interview
    if _interview is None:
        _interview = build_agent_graph(
            tools=get_interview_tools(),
            system_prompt=INTERVIEW_SYSTEM_PREFIX,
            recall_mode="interview",
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
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_stream_agent_executor(temperature=temperature, enable_web_search=enable_web_search)
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        memory=memory,
    ):
        yield evt


async def stream_interview_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_stream_interview_executor(temperature=temperature)
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        memory=memory,
    ):
        yield evt
