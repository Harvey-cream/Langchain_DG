"""企业知识库线：MCP 工具装配与向量库预热（RAG 召回在 skill_recall 节点）。"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend_langchain.logger_func import log_exception_event
from common.rag import warmup

logger = logging.getLogger(__name__)


def warmup_knowledge_stores() -> None:
    warmup()
    try:
        from MCP.mcp_multiserver import load_mcp_tools_once

        load_mcp_tools_once()
    except Exception:
        log_exception_event(logger, "warmup_knowledge_mcp_preload_failed")


def _is_web_search_tool(tool_obj: object) -> bool:
    """百炼 WebSearch MCP / 旧 Tavily 等联网搜索工具。"""
    name = str(getattr(tool_obj, "name", "") or "").strip().lower()
    return "tavily" in name or "web_search" in name or "websearch" in name


def _mcp_tool_with_sync_invoke(tool: object) -> object:
    from langchain_core.tools.structured import StructuredTool

    if not isinstance(tool, StructuredTool):
        return tool
    if getattr(tool, "func", None) is not None:
        return tool
    coro = getattr(tool, "coroutine", None)
    if coro is None:
        return tool

    def _sync(*args: Any, **kwargs: Any) -> Any:
        async def _call() -> Any:
            return await coro(*args, **kwargs)

        def _isolated_run() -> Any:
            return asyncio.run(_call())

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _isolated_run()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_isolated_run).result()

    try:
        return tool.model_copy(update={"func": _sync})
    except Exception:  # noqa: BLE001
        log_exception_event(logger, "mcp_tool_sync_adapter_failed", tool_name=getattr(tool, "name", None))
        return tool


def get_all_agent_tools(*, enable_web_search: bool = False) -> list:
    """知识问答 Agent：PDF HITL + MCP（联网由强制预搜注入，不挂给模型）。"""
    from common.tools import get_builtin_pdf_tools
    from MCP.mcp_multiserver import load_mcp_tools_once

    _ = enable_web_search  # 兼容旧调用签名
    mcp_tools = [_mcp_tool_with_sync_invoke(t) for t in load_mcp_tools_once()]
    mcp_tools = [t for t in mcp_tools if not _is_web_search_tool(t)]
    return get_builtin_pdf_tools() + mcp_tools


def get_summary_tools() -> list:
    """文档摘要 Agent：不挂 MCP；摘要依赖 RAG 注入，避免工具面干扰。"""
    return []
