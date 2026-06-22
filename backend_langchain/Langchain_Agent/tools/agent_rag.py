from __future__ import annotations

import asyncio
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, List

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool

from backend_langchain.logger_func import log_exception_event
from common.embedding import get_embedding_model

logger = logging.getLogger(__name__)
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_COLLECTION_NAME = "md_knowledge"
_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
_TOP_K = 5

_STORE_AI_PROGRAMMING = "AI_programming"
_STORE_OPENCLAW = "Openclaw"
_STORE_VIBE_CODING = "Vibecoding"
_STORE_LEARNING_INTERVIEW = "Learn_programing"

_CHROMA_SUBDIRS: tuple[str, ...] = (
    _STORE_AI_PROGRAMMING,
    _STORE_OPENCLAW,
    _STORE_VIBE_CODING,
    _STORE_LEARNING_INTERVIEW,
)

_chroma_store_cache: dict[str, Chroma] = {}
_chroma_lock = threading.Lock()


def _chroma_root() -> Path:
    return Path(__file__).resolve().parents[2] / "Langchain_knowledge" / "chroma_db"


def _get_embeddings() -> Embeddings:
    return get_embedding_model(_EMBEDDING_MODEL, device="cpu", normalize_embeddings=True, batch_size=32)


def _get_chroma_store(persist_subdir: str) -> Chroma | None:
    global _chroma_store_cache
    root = _chroma_root() / persist_subdir
    if not root.is_dir():
        return None
    if persist_subdir not in _chroma_store_cache:
        with _chroma_lock:
            if persist_subdir not in _chroma_store_cache:
                _chroma_store_cache[persist_subdir] = Chroma(
                    collection_name=_COLLECTION_NAME,
                    persist_directory=str(root),
                    embedding_function=_get_embeddings(),
                )
    return _chroma_store_cache[persist_subdir]


def warmup_rag_singletons() -> None:
    _get_embeddings()
    for sub in _CHROMA_SUBDIRS:
        _get_chroma_store(sub)
    try:
        from MCP.mcp_multiserver import load_mcp_tools_once

        load_mcp_tools_once()
    except Exception:
        log_exception_event(logger, "warmup_rag_singletons_mcp_preload_failed")


def _format_docs(docs) -> str:
    if not docs:
        return "未检索到相关知识片段。"
    parts: List[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        kb = (meta.get("knowledge_base") or "资料").strip()
        content = (doc.page_content or "").strip()[:1200]
        parts.append(f"【片段{i}·{kb}】\n{content}")
    return "\n\n".join(parts)


def _rag_similarity_search(persist_subdir: str, query: str) -> str:
    vs = _get_chroma_store(persist_subdir)
    if vs is None:
        root = _chroma_root() / persist_subdir
        return (
            f"向量库目录不存在或未构建：{root}。"
            f"请在 backend_langchain 下运行：python Scripts/build_md_knowledge.py"
        )
    return _format_docs(vs.similarity_search(query.strip(), k=_TOP_K))


@tool("rag_ai_programming")
def rag_ai_programming(query: str) -> str:
    """检索「AI 编程工具与实战」向量知识库。"""
    return _rag_similarity_search(_STORE_AI_PROGRAMMING, query)


@tool("rag_openclaw")
def rag_openclaw(query: str) -> str:
    """检索「OpenClaw 保姆级教程」向量知识库。"""
    return _rag_similarity_search(_STORE_OPENCLAW, query)


@tool("rag_vibe_coding")
def rag_vibe_coding(query: str) -> str:
    """检索「Vibe Coding 零基础教程」向量知识库。"""
    return _rag_similarity_search(_STORE_VIBE_CODING, query)


@tool("rag_learning_interview")
def rag_learning_interview(query: str) -> str:
    """检索「编程学习路线与面试」向量知识库。"""
    return _rag_similarity_search(_STORE_LEARNING_INTERVIEW, query)


RAG_TOOLS = [rag_ai_programming, rag_openclaw, rag_vibe_coding, rag_learning_interview]


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
    return list(RAG_TOOLS) + [confirm_pdf_export, finalize_pdf_export] + mcp_tools
