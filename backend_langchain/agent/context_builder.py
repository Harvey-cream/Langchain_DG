"""Context Builder：图前并行准备 History 读 / Memory / Retrieval Planner→RAG。

History 压缩写 checkpoint 在 gather 之外串行执行（读并行、写串行）。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph

from agent.graph_factory import format_recent_dialogue
from agent.memory.memory_persist import MemoryTurnContext
from backend_langchain.logger_func import log_info_event, log_warning_event

logger = logging.getLogger(__name__)

RecallMode = Literal["main", "interview"]


@dataclass
class TurnContext:
    """本轮预计算结果，经 configurable.turn_context 与 AgentState 注入图。"""

    need_rag: bool = False
    search_questions: list[str] = field(default_factory=list)
    rag_done: bool = False
    memory_injected: bool = False
    retrieved_context: str = ""
    memory_text: str = ""
    recent_dialogue: str = ""


def turn_context_from_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """从 RunnableConfig / configurable 取出 turn_context dict。"""
    if not config:
        return {}
    cfg = config.get("configurable") if "configurable" in config else config
    if not isinstance(cfg, dict):
        return {}
    tc = cfg.get("turn_context")
    return tc if isinstance(tc, dict) else {}


def turn_context_as_dict(tc: TurnContext) -> dict[str, Any]:
    return {
        "need_rag": tc.need_rag,
        "search_questions": list(tc.search_questions),
        "rag_done": tc.rag_done,
        "memory_injected": tc.memory_injected,
    }


async def _history_manager_read(
    agent: CompiledStateGraph,
    thread_id: str,
) -> tuple[list[BaseMessage], str]:
    """只读 checkpoint messages，供改写补全指代；不写压缩。"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = await agent.aget_state(config)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "context_history_read_failed",
            thread_id=thread_id,
            error=str(e),
        )
        return [], ""
    state_values = getattr(snapshot, "values", None) or {}
    messages = list(state_values.get("messages") or [])
    return messages, format_recent_dialogue(messages)


async def _memory_retriever(
    *,
    user_id: int,
    query: str,
) -> str:
    try:
        from agent.memory.long_term_agent import format_retrieved_memories

        return await asyncio.to_thread(format_retrieved_memories, user_id, query)
    except Exception as e:  # noqa: BLE001
        log_warning_event(
            logger,
            "context_memory_retrieve_failed",
            user_id=user_id,
            error=str(e),
        )
        return ""


async def _retrieval_planner_and_search(
    user_text: str,
    *,
    mode: RecallMode,
    recent_dialogue: str,
    user_id: int | None,
) -> tuple[bool, list[str], str, bool]:
    """Planner → 按需 RAG。返回 (need_rag, questions, retrieved, rag_done)。"""
    from agent.rag.rag import retrieve_context
    from agent.rag.retrieval_planner import plan_retrieval
    from config.config import CORPUS_INTERVIEW, CORPUS_USER

    text = (user_text or "").strip()
    if not text:
        return False, [], "", False

    plan = await plan_retrieval(
        text,
        mode=mode,
        skill_name=None,
        recent_dialogue=recent_dialogue,
    )
    if not plan.need_rag:
        return False, [], "", True  # planned: no search needed

    questions = plan.search_questions or [text]
    try:
        if mode == "interview":
            retrieved = await asyncio.to_thread(
                retrieve_context, questions, corpus=CORPUS_INTERVIEW
            )
        else:
            retrieved = await asyncio.to_thread(
                retrieve_context,
                questions,
                corpus=CORPUS_USER,
                user_id=user_id,
            )
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "context_rag_search_failed", error=str(e))
        return True, questions, "", True

    return True, questions, retrieved or "", True


async def build_turn_context(
    agent: CompiledStateGraph,
    *,
    prompt_text: str,
    thread_id: str,
    mode: RecallMode = "main",
    memory: MemoryTurnContext | None = None,
) -> TurnContext:
    """并行：History 读 || Memory 读 ||（等 History 对话后）Planner→RAG。

    实际调度：先 gather(History读, Memory)；再 Planner→RAG（依赖 recent_dialogue）；
    调用方负责随后串行 maybe_compress_history。
    """
    user_id = int(memory.user_id) if memory is not None else 0
    text = (prompt_text or "").strip()

    async def _mem() -> str:
        if user_id <= 0 or not text:
            return ""
        return await _memory_retriever(user_id=user_id, query=text)

    # History 读与 Memory 并行；History 完成后立刻开 Planner→RAG，与 Memory 剩余时间重叠
    hist_task = asyncio.create_task(_history_manager_read(agent, thread_id))
    mem_task = asyncio.create_task(_mem())
    _messages, recent_dialogue = await hist_task
    rag_task = asyncio.create_task(
        _retrieval_planner_and_search(
            text,
            mode=mode,
            recent_dialogue=recent_dialogue,
            user_id=user_id if user_id > 0 else None,
        )
    )
    memory_text, rag_pack = await asyncio.gather(mem_task, rag_task)
    need_rag, questions, retrieved, rag_done = rag_pack

    tc = TurnContext(
        need_rag=need_rag,
        search_questions=questions,
        rag_done=rag_done,
        memory_injected=bool((memory_text or "").strip()),
        retrieved_context=retrieved,
        memory_text=memory_text or "",
        recent_dialogue=recent_dialogue,
    )
    log_info_event(
        logger,
        "context_builder_ok",
        mode=mode,
        need_rag=need_rag,
        rag_done=rag_done,
        memory_injected=tc.memory_injected,
        retrieved_chars=len(tc.retrieved_context),
    )
    return tc
