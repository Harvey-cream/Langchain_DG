"""pgvector RAG：单表 rag_embeddings，corpus 区分内置库 knowledge 与用户上传库 user_knowledge。"""
from __future__ import annotations

import threading
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from agent.rag.embedding import get_rag_embedding_model
from agent.rag.pgvector_store import PgVectorStore
from config.config import (
    COLLECTION,
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    CORPUS_USER,
    RECALL_K,
    USER_COLLECTION,
    dashscope_dimensions,
    get_domains,
)

_store: PgVectorStore | None = None
_store_lock = threading.Lock()
_embeddings: Embeddings | None = None

_NO_HITS_MSG = "未检索到足够相关的知识片段。"
_NOT_BUILT_MSG = (
    "向量库未构建或为空。请在 backend_langchain 下运行："
    "python Scripts/build_rag_knowledge.py"
)


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = get_rag_embedding_model()
    return _embeddings


def _get_store() -> PgVectorStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                from app.settings import VECTOR_POSTGRES_URL

                _store = PgVectorStore(
                    _get_embeddings(),
                    dim=dashscope_dimensions(),
                    dsn=VECTOR_POSTGRES_URL,
                )
    return _store


def get_store() -> PgVectorStore:
    """内置知识库 + 用户库共用同一张表（corpus 区分）。"""
    store = _get_store()
    store.setup()
    return store


# 兼容旧调用点（Chroma 时代分内置/用户两个 store，现统一为一张表）
get_or_create_store = get_store
get_user_store = get_store
get_or_create_user_store = get_store


def warmup() -> None:
    _get_embeddings()
    _get_store().setup()


def format_hits(docs: list[Document]) -> str:
    if not docs:
        return _NO_HITS_MSG
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        sp = (meta.get("source_path") or "").strip()
        title = Path(sp).name if sp else ""
        head = f"[{i}] {title}".strip()
        body = (doc.page_content or "").strip()[:1500]
        parts.append(f"{head}\n{body}")
    return "\n\n".join(parts)


def search_hits(
    query: str,
    *,
    corpus: str,
    top_k: int = RECALL_K,
    user_id: int | None = None,
) -> list[tuple[Document, float]]:
    """向量召回，返回 (Document, distance)；distance 越小越相似。相关性交给后续精排。"""
    q = (query or "").strip()
    if not q:
        return []

    if corpus not in get_domains():
        return []
    if corpus == CORPUS_USER and user_id is None:
        return []

    return _get_store().similarity_search_with_score(
        q,
        k=top_k,
        corpus=corpus,
        user_id=user_id if corpus == CORPUS_USER else None,
    )


def _doc_key(doc: Document) -> str:
    meta = doc.metadata or {}
    sp = str(meta.get("source_path") or "")
    body = (doc.page_content or "").strip()
    return f"{sp}\n{body[:200]}"


def _merge_hits(hits_batches: list[list[tuple[Document, float]]]) -> list[tuple[Document, float]]:
    best: dict[str, tuple[Document, float]] = {}
    for hits in hits_batches:
        for doc, dist in hits:
            key = _doc_key(doc)
            prev = best.get(key)
            if prev is None or dist < prev[1]:
                best[key] = (doc, dist)
    return sorted(best.values(), key=lambda x: x[1])


def retrieve_context(
    questions: list[str],
    *,
    corpus: str,
    recall_k: int | None = None,
    rerank_top_k: int | None = None,
    user_id: int | None = None,
) -> str:
    """多问句粗召回 → 去重合并 → DashScope 精排 → 格式化注入上下文。

    - corpus=user：只查用户上传库（corpus=user + user_id）
    - corpus=agent/interview：只查内置 knowledge
    """
    from agent.rag.rerank import rerank_documents

    qs = [q.strip() for q in questions if (q or "").strip()]
    if not qs:
        return "检索关键词为空。"

    if corpus not in get_domains():
        return f"未知 corpus={corpus!r}"

    k_recall = RECALL_K if recall_k is None else recall_k

    if corpus == CORPUS_USER:
        if user_id is None:
            return _NO_HITS_MSG
        batches = [
            search_hits(q, corpus=CORPUS_USER, top_k=k_recall, user_id=user_id)
            for q in qs
        ]
    else:
        if _get_store().count(corpus=corpus) == 0:
            return _NOT_BUILT_MSG
        batches = [search_hits(q, corpus=corpus, top_k=k_recall) for q in qs]

    merged = _merge_hits(batches)
    if not merged:
        return _NO_HITS_MSG

    ranked = rerank_documents(qs[0], merged, top_k=rerank_top_k)
    if not ranked:
        return _NO_HITS_MSG
    return format_hits(ranked)


__all__ = [
    "COLLECTION",
    "USER_COLLECTION",
    "CORPUS_AGENT",
    "CORPUS_INTERVIEW",
    "CORPUS_USER",
    "format_hits",
    "get_store",
    "get_or_create_store",
    "get_user_store",
    "get_or_create_user_store",
    "retrieve_context",
    "search_hits",
    "warmup",
]
