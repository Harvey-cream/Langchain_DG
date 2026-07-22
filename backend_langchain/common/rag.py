"""Chroma RAG：内置库 knowledge + 用户上传库 user_knowledge 分离。"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from common.embedding import get_rag_embedding_model
from config.config import (
    COLLECTION,
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    CORPUS_USER,
    RECALL_K,
    USER_COLLECTION,
    chroma_path,
    get_domains,
    user_chroma_path,
)

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_store: Chroma | None = None
_user_store: Chroma | None = None
_store_lock = threading.Lock()
_user_store_lock = threading.Lock()
_embeddings: Embeddings | None = None

_NO_HITS_MSG = "未检索到足够相关的知识片段。"


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = get_rag_embedding_model()
    return _embeddings


def get_store() -> Chroma | None:
    """内置知识库（docs1/docs2 → collection=knowledge）。"""
    global _store
    path = chroma_path()
    if not path.is_dir():
        return None
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = Chroma(
                    collection_name=COLLECTION,
                    persist_directory=str(path),
                    embedding_function=_get_embeddings(),
                )
    return _store


def get_or_create_store() -> Chroma:
    """确保内置 knowledge 库目录存在（建库脚本用）。"""
    global _store
    path = chroma_path()
    path.mkdir(parents=True, exist_ok=True)
    store = get_store()
    if store is not None:
        return store
    with _store_lock:
        if _store is None:
            _store = Chroma(
                collection_name=COLLECTION,
                persist_directory=str(path),
                embedding_function=_get_embeddings(),
            )
        return _store


def get_user_store() -> Chroma | None:
    """用户上传文档库；目录不存在则视为尚未入库。"""
    global _user_store
    path = user_chroma_path()
    if not path.is_dir():
        return None
    if _user_store is None:
        with _user_store_lock:
            if _user_store is None:
                _user_store = Chroma(
                    collection_name=USER_COLLECTION,
                    persist_directory=str(path),
                    embedding_function=_get_embeddings(),
                )
    return _user_store


def get_or_create_user_store() -> Chroma:
    """用户上传写入专用库（与 knowledge 完全隔离）。"""
    global _user_store
    path = user_chroma_path()
    path.mkdir(parents=True, exist_ok=True)
    store = get_user_store()
    if store is not None:
        return store
    with _user_store_lock:
        if _user_store is None:
            _user_store = Chroma(
                collection_name=USER_COLLECTION,
                persist_directory=str(path),
                embedding_function=_get_embeddings(),
            )
        return _user_store


def warmup() -> None:
    _get_embeddings()
    get_store()
    get_user_store()


def _where(corpus: str, *, user_id: int | None = None) -> dict:
    # Chroma 新版本 where 顶层只能有一个算子；多条件用 $and + $eq
    if corpus == CORPUS_USER and user_id is not None:
        return {"user_id": {"$eq": str(user_id)}}
    return {"corpus": {"$eq": corpus}}


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

    store = get_user_store() if corpus == CORPUS_USER else get_store()
    if store is None:
        return []

    pairs = store.similarity_search_with_score(
        q, k=top_k, filter=_where(corpus, user_id=user_id)
    )
    return [(doc, float(score)) for doc, score in pairs]


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

    - corpus=user：只查用户上传库 user_knowledge（需 user_id）
    - corpus=agent/interview：只查内置 knowledge
    """
    from common.rerank import rerank_documents

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
        if get_store() is None:
            return (
                f"向量库未构建：{chroma_path()}。"
                "请在 backend_langchain 下运行：python Scripts/build_rag_knowledge.py"
            )
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
    "chroma_path",
    "user_chroma_path",
    "format_hits",
    "get_store",
    "get_or_create_store",
    "get_user_store",
    "get_or_create_user_store",
    "retrieve_context",
    "search_hits",
    "warmup",
]
