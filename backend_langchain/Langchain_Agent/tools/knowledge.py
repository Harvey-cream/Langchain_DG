"""知识检索工具：单入口 + metadata 域过滤。"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.tools import tool

from backend_langchain.logger_func import log_exception_event
from config.config import CORPUS_AGENT, CORPUS_INTERVIEW
from common.rag import search, warmup

logger = logging.getLogger(__name__)

@tool("search_knowledge")
def search_knowledge(query: str, domain: str | None = None) -> str:
    """检索主助手知识库。domain 为 docs1 下子目录名（如 ai_programming）；不传则搜全库。"""
    return search(query, corpus=CORPUS_AGENT, domain=domain)


@tool("search_interview_bank")
def search_interview_bank(query: str, domain: str | None = None) -> str:
    """检索面试题库。domain 为 docs2 下子目录名（如 interview_llm）；不传则搜全库。"""
    return search(query, corpus=CORPUS_INTERVIEW, domain=domain)


def warmup_knowledge_stores() -> None:
    warmup()
    try:
        from MCP.mcp_multiserver import load_mcp_tools_once

        load_mcp_tools_once()
    except Exception:
        log_exception_event(logger, "warmup_knowledge_mcp_preload_failed")


def _is_tavily_tool(tool_obj: object) -> bool:
    name = str(getattr(tool_obj, "name", "") or "").strip().lower()
    return "tavily" in name or "web_search" in name


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
    from human_in_the_loop.human_loop import confirm_pdf_export, finalize_pdf_export
    from MCP.mcp_multiserver import load_mcp_tools_once

    mcp_tools = [_mcp_tool_with_sync_invoke(t) for t in load_mcp_tools_once()]
    if not enable_web_search:
        mcp_tools = [t for t in mcp_tools if not _is_tavily_tool(t)]
    return [search_knowledge, confirm_pdf_export, finalize_pdf_export] + mcp_tools


def get_interview_tools() -> list:
    from human_in_the_loop.human_loop import confirm_pdf_export, finalize_pdf_export

    return [search_interview_bank, confirm_pdf_export, finalize_pdf_export]
