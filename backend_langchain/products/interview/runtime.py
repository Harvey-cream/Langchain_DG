"""面试 Agent 线：入口图组装与流式调用（与企业知识库线隔离）。

当前仍是单图 + skill_recall；后续可在本文件演进为线内 Supervisor + 子图（JD→模拟→评估）。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from products.interview.memory.memory_persist import MemoryTurnContext
from products.interview.pdf.schema_tools import get_builtin_pdf_tools
from products.interview.agent.execution.graph_factory import build_agent_graph
from products.interview.agent.streaming.stream import stream_graph_chat_model_events
from products.interview.prompts import INTERVIEW_SYSTEM_PREFIX
from products.interview.skills import INTERVIEW_SKILLS

_interview: CompiledStateGraph | None = None


def reset_interview_agent_cache() -> None:
    """代码热重载后清面试线图缓存，避免仍用旧节点/工具编译结果。"""
    global _interview
    _interview = None


def get_stream_interview_executor(*, temperature: float = 0.45) -> CompiledStateGraph:
    """面试大师图：Workflow RAG + PDF，不挂 MCP。"""
    global _interview
    if _interview is None:
        _interview = build_agent_graph(
            tools=get_builtin_pdf_tools(),
            system_prompt=INTERVIEW_SYSTEM_PREFIX,
            recall_mode="interview",
            skills=INTERVIEW_SKILLS,
            temperature=temperature,
            streaming=True,
        )
    return _interview


async def stream_interview_agent(
    *,
    prompt_text: str = "",
    thread_id: str,
    temperature: float = 0.45,
    resume_pdf: bool | None = None,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
) -> AsyncIterator[dict[str, Any]]:
    agent = get_stream_interview_executor(temperature=temperature)
    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=prompt_text,
        thread_id=thread_id,
        resume_pdf=resume_pdf,
        attachments=attachments,
        memory=memory,
        recall_mode="interview",
    ):
        yield evt
