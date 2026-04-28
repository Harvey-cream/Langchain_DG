from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import List

from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langchain_chroma import Chroma

from common.embedding import get_embedding_model
from human_in_the_loop.human_loop import confirm_pdf_export, finalize_pdf_export

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_COLLECTION_NAME = "md_knowledge"
_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
_TOP_K = 5

# chroma_db1 子目录名（与构建脚本/本地目录一致）
_STORE_AI_LLM_INTERVIEW = "AI大模型原理和应用面试题"
_STORE_JAVA_INTERVIEW = "Java 热门面试题"
_STORE_VUE_INTERVIEW = "前端Vue 基础面试题速"

_CHROMA_INTERVIEW_SUBDIRS: tuple[str, ...] = (
    _STORE_AI_LLM_INTERVIEW,
    _STORE_JAVA_INTERVIEW,
    _STORE_VUE_INTERVIEW,
)

_chroma_store_cache: dict[str, Chroma] = {}
_chroma_lock = threading.Lock()


def _chroma_root() -> Path:
    """…/Langchain_knowledge/chroma_db1"""
    return Path(__file__).resolve().parents[2] / "backend_langchain" / "Langchain_knowledge" / "chroma_db1"


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


def warmup_interview_rag_singletons() -> None:
    """进程内预热：嵌入 + 三套面试向量库。"""
    _get_embeddings()
    for sub in _CHROMA_INTERVIEW_SUBDIRS:
        _get_chroma_store(sub)


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
            f"请在 backend_langchain 下用对应文档构建 chroma_db1 子目录。"
        )
    docs = vs.similarity_search(query.strip(), k=_TOP_K)
    return _format_docs(docs)


@tool("rag_interview_ai_llm")
def rag_interview_ai_llm(query: str) -> str:
    """检索「AI 大模型原理与应用」面试题向量库。

    适用场景：大模型架构、训练/推理、RAG、Agent、提示工程、应用落地与常见八股。
    输入：用自然语言描述考点或问题（中文为主）。
    输出：带溯源字段的若干片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_AI_LLM_INTERVIEW, query)


@tool("rag_interview_java")
def rag_interview_java(query: str) -> str:
    """检索「Java 热门面试题」向量库。

    适用场景：Java 语言基础、集合与并发、JVM、Spring 相关高频面试问答。
    输入：用自然语言描述考点或问题。
    输出：带溯源字段的若干片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_JAVA_INTERVIEW, query)


@tool("rag_interview_vue")
def rag_interview_vue(query: str) -> str:
    """检索「前端 Vue 基础」面试题向量库。

    适用场景：Vue 基础、组件、响应式、路由、组合式 API 等常见面试问答。
    输入：用自然语言描述考点或问题。
    输出：带溯源字段的若干片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_VUE_INTERVIEW, query)


INTERVIEW_RAG_TOOLS = [
    rag_interview_ai_llm,
    rag_interview_java,
    rag_interview_vue,
    confirm_pdf_export,
    finalize_pdf_export,
]
