"""企业知识库 AI 助手线：总控 Supervisor Graph + 对外流式入口（与面试线隔离）。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from agent.graph_factory import stream_graph_chat_model_events
from agent.memory.memory_persist import MemoryTurnContext
from agent.graphs.supervisor_knowledge import build_knowledge_supervisor_graph

_supervisor_local: CompiledStateGraph | None = None
_supervisor_web: CompiledStateGraph | None = None


def reset_knowledge_agent_cache() -> None:
    """代码热重载后清知识库线总控图缓存。"""
    global _supervisor_local, _supervisor_web
    _supervisor_local = None
    _supervisor_web = None


def get_knowledge_supervisor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """知识库线总控图：LLM route → 文档摘要 / 知识问答 子图。"""
    global _supervisor_local, _supervisor_web
    if enable_web_search:
        if _supervisor_web is None:
            _supervisor_web = build_knowledge_supervisor_graph(
                temperature=temperature,
                enable_web_search=True,
            )
        return _supervisor_web
    if _supervisor_local is None:
        _supervisor_local = build_knowledge_supervisor_graph(
            temperature=temperature,
            enable_web_search=False,
        )
    return _supervisor_local


def get_stream_agent_executor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    """兼容旧调用名：返回知识库总控图。"""
    return get_knowledge_supervisor(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )


# 兼容旧 warmup / 脚本：指向总控内已编译的子能力入口名
def get_knowledge_qa_executor(
    *,
    temperature: float = 0.45,
    enable_web_search: bool = False,
) -> CompiledStateGraph:
    return get_knowledge_supervisor(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )


def get_doc_summary_executor(*, temperature: float = 0.45) -> CompiledStateGraph:
    return get_knowledge_supervisor(temperature=temperature, enable_web_search=False)


async def stream_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    enable_web_search: bool = False,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_knowledge_supervisor(
        temperature=temperature,
        enable_web_search=enable_web_search,
    )
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        attachments=attachments,
        memory=memory,
        recall_mode="main",
    ):
        yield evt
