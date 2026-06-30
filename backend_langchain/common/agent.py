"""LangGraph Agent 核心：手写两节点图（方案 B）、checkpoint、异步流式事件解析。

构图刻意保持显式：agent_node 调模型、ToolNode 跑工具、tools_condition 决定是否再循环。
两个 Agent（主对话 / 面试）共用本文件的 `build_agent_graph`，仅传入不同的 tools 与 system_prompt。
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from typing_extensions import TypedDict

from Agent_memory.memory import maybe_compress_history
from human_in_the_loop.human_loop import interrupt_payload_from_updates
from backend_langchain.logger_func import log_warning_event

# 兼容直接以脚本方式运行（cwd=backend_langchain）时的包路径。
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)


# =============================================================================
# Checkpointer（AsyncSqliteSaver，主/面试按 thread_id 分区共享一份）
# =============================================================================

CHECKPOINT_SQLITE_PATH = Path(__file__).resolve().parent / "data" / "langgraph_checkpoints.sqlite3"
_checkpointer: AsyncSqliteSaver | None = None
_checkpointer_ctx: Any = None


async def init_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer is None:
        CHECKPOINT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_SQLITE_PATH))
        _checkpointer = await _checkpointer_ctx.__aenter__()
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
    _checkpointer = None
    _checkpointer_ctx = None


def get_checkpointer() -> AsyncSqliteSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer 未初始化，请在应用 lifespan 中调用 init_checkpointer()")
    return _checkpointer


def agent_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"agent:{user_id}:{conversation_id}"


def interview_checkpoint_thread_id(user_id: int, conversation_id: int) -> str:
    return f"interview:{user_id}:{conversation_id}"


# =============================================================================
# 工具函数
# =============================================================================


def message_content_to_text(content: Any) -> str:
    """LangChain 消息 content 可能是 str 或多模态 block 列表，统一抽成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


def _graph_recursion_limit() -> int:
    """封顶 LangGraph 步数：每轮约 model+tool 两步，默认够 6 轮工具调用，可用环境变量覆盖。"""
    raw = os.getenv("AGENT_RECURSION_LIMIT", "").strip()
    if raw.isdigit():
        return max(4, int(raw))
    return 16


def _graph_config(thread_id: str) -> dict[str, Any]:
    return {"recursion_limit": _graph_recursion_limit(), "configurable": {"thread_id": thread_id}}


# =============================================================================
# 方案 B：手写两节点图（agent ↔ tools），主/面试各编译一张
# =============================================================================


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_agent_graph(
    *,
    tools: Sequence[Any],
    system_prompt: str,
    temperature: float = 0.45,
    streaming: bool = False,
) -> CompiledStateGraph:
    """编译一张 LangGraph 图：system_prompt 每轮注入，工具由 ToolNode 执行（含 PDF interrupt）。"""
    tools_list = list(tools)
    model = get_qwen_chat_model(temperature=temperature, streaming=streaming)
    if tools_list:
        model = model.bind_tools(tools_list)
    system_message = SystemMessage(content=system_prompt)

    async def agent_node(state: AgentState) -> dict[str, list[BaseMessage]]:
        gathered: BaseMessage | None = None
        async for chunk in model.astream([system_message, *state["messages"]]):
            if text := message_content_to_text(getattr(chunk, "content", None)):
                get_stream_writer()({"type": "delta", "text": text})
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]
        if gathered is None:
            return {"messages": []}
        return {"messages": [gathered]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools_list))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=get_checkpointer())


# =============================================================================
# 异步流式：custom（节点/工具 writer）+ updates（interrupt）
# =============================================================================


async def _compress_history_safely(agent: CompiledStateGraph, thread_id: str) -> None:
    try:
        await maybe_compress_history(agent, thread_id=thread_id)
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "memory_compress_skipped", thread_id=thread_id, error=str(e))


_SEARCH_TOOLS = frozenset({"search_knowledge", "search_interview_bank"})


def _search_status_from_updates(payload: Any) -> str | None:
    """agent 决定调检索工具时，在 updates 层推通用状态（工具内不调 get_stream_writer）。"""
    if not isinstance(payload, dict):
        return None
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        return None
    msgs = agent.get("messages") or []
    if not msgs:
        return None
    last = msgs[-1]
    for tc in getattr(last, "tool_calls", None) or []:
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
        if name in _SEARCH_TOOLS:
            return "正在搜索..."
    return None


async def stream_graph_chat_model_events(
    agent: CompiledStateGraph,
    *,
    prompt_text: str = "",
    thread_id: str,
    resume_pdf: bool | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """流式产出事件：delta / status / interrupt / pdf_ready（custom + updates）。"""
    if resume_pdf is not None:
        graph_input: Any = Command(resume=resume_pdf)
    else:
        await _compress_history_safely(agent, thread_id)
        graph_input = {"messages": [HumanMessage(content=prompt_text)]}

    seen_pdf: set[tuple[str, str]] = set()

    async for mode, payload in agent.astream(
        graph_input, _graph_config(thread_id), stream_mode=["custom", "updates"]
    ):
        if mode == "custom" and isinstance(payload, dict):
            t = payload.get("type")
            if t in ("status", "delta") and payload.get("text") is not None:
                yield {"type": t, "text": str(payload["text"])}
            elif t == "pdf_ready" and payload.get("url"):
                key = (str(payload["url"]), str(payload.get("filename") or "export.pdf"))
                if key in seen_pdf:
                    continue
                seen_pdf.add(key)
                yield {"type": "pdf_ready", "url": key[0], "filename": key[1]}
            continue

        if mode == "updates":
            if isinstance(payload, dict) and (status := _search_status_from_updates(payload)):
                yield {"type": "status", "text": status}
            intr = interrupt_payload_from_updates(payload)
            if intr:
                yield {"type": "interrupt", **intr}


def warmup_agent_executors(*, temperature: float = 0.45) -> None:
    """进程启动时预热三张流式图（主对话本地/联网 + 面试），避免首请求冷启动。"""
    from Langchain_Agent import agents

    agents.reset_stream_agent_cache()
    agents.get_stream_agent_executor(temperature=temperature, enable_web_search=False)
    agents.get_stream_agent_executor(temperature=temperature, enable_web_search=True)
    agents.get_stream_interview_executor(temperature=temperature)
