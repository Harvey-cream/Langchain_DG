"""异步流式：custom（节点/工具 writer）+ updates（interrupt）。

产品线无关：任何 CompiledStateGraph 都可通过本模块产出统一事件。
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from backend_langchain.logger_func import log_warning_event
from infrastructure.memory.memory import maybe_compress_history
from infrastructure.memory.memory_persist import MemoryTurnContext
from infrastructure.pdf.human_loop import interrupt_payload_from_updates
from runtime.execution.graph_factory import RecallModeParam

logger = logging.getLogger(__name__)


def _graph_recursion_limit() -> int:
    """封顶 LangGraph 步数：每轮约 model+tool 两步，默认够 6 轮工具调用，可用环境变量覆盖。"""
    raw = os.getenv("AGENT_RECURSION_LIMIT", "").strip()
    if raw.isdigit():
        return max(4, int(raw))
    return 16


def _graph_config(thread_id: str) -> dict[str, Any]:
    return {"recursion_limit": _graph_recursion_limit(), "configurable": {"thread_id": thread_id}}


def _split_astream_item(item: Any) -> tuple[Any, Any]:
    """统一解包 astream 项。

    - stream_mode 为列表且 subgraphs=False → (mode, data)
    - stream_mode 为列表且 subgraphs=True  → (namespace, mode, data)
    """
    if isinstance(item, tuple) and len(item) == 3:
        return item[1], item[2]
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1]
    return None, item


async def _compress_history_safely(
    agent: CompiledStateGraph,
    thread_id: str,
    *,
    memory: MemoryTurnContext | None = None,
) -> None:
    try:
        await maybe_compress_history(agent, thread_id=thread_id, memory=memory)
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "memory_compress_skipped", thread_id=thread_id, error=str(e))


async def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str = "",
    thread_id: str,
    resume_pdf: bool | None = None,
    attachments: list[dict] | None = None,
    memory: MemoryTurnContext | None = None,
    recall_mode: RecallModeParam = "main",
) -> AsyncIterator[dict[str, Any]]:
    """流式产出事件：delta / status / web_sources / interrupt / pdf_ready（custom + updates）。

    图前 Context Builder：History 读 || Memory || Retrieval Planner→RAG；
    History 压缩写在 gather 后串行。总控挂载子图时必须 subgraphs=True。
    """
    from runtime.context.builder import (
        build_turn_context,
        turn_context_as_dict,
    )

    if resume_pdf is not None:
        graph_input: Any = Command(resume=resume_pdf)
        config = _graph_config(thread_id)
        if attachments:
            config["configurable"]["attachments"] = attachments
    else:
        # 1) Context Builder（读并行）
        turn_ctx = await build_turn_context(
            agent,
            prompt_text=prompt_text,
            thread_id=thread_id,
            mode=recall_mode,
            memory=memory,
        )
        # 2) History 写串行
        await _compress_history_safely(agent, thread_id, memory=memory)

        turn_messages: list[Any] = []
        if turn_ctx.memory_text.strip():
            turn_messages.append(SystemMessage(content=turn_ctx.memory_text))
        turn_messages.append(HumanMessage(content=prompt_text))
        graph_input = {
            "messages": turn_messages,
            "skill_name": "",
            "skill_context": "",
            "retrieved_context": turn_ctx.retrieved_context,
            "web_context": "",
            "next_agent": "",
        }

        config = _graph_config(thread_id)
        config["configurable"]["turn_context"] = turn_context_as_dict(turn_ctx)
        if attachments:
            config["configurable"]["attachments"] = attachments

    seen_pdf: set[tuple[str, str]] = set()

    async for item in agent.astream(
        graph_input,
        config,
        stream_mode=["custom", "updates"],
        subgraphs=True,
    ):
        mode, payload = _split_astream_item(item)
        if mode == "custom" and isinstance(payload, dict):
            t = payload.get("type")
            if t in ("status", "delta") and payload.get("text") is not None:
                yield {"type": t, "text": str(payload["text"])}
            elif t == "web_sources" and isinstance(payload.get("sources"), list):
                yield {"type": "web_sources", "sources": payload["sources"]}
            elif t == "pdf_ready" and payload.get("url"):
                key = (str(payload["url"]), str(payload.get("filename") or "export.pdf"))
                if key in seen_pdf:
                    continue
                seen_pdf.add(key)
                yield {"type": "pdf_ready", "url": key[0], "filename": key[1]}
            continue

        if mode == "updates":
            intr = interrupt_payload_from_updates(payload)
            if intr:
                yield {"type": "interrupt", **intr}
