"""统一 Chroma RAG：单 collection，corpus + domain metadata 隔离。"""
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
    RAG_MAX_DISTANCE,
    RECALL_K,
    chroma_path,
    get_domains,
)

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_store: Chroma | None = None
_store_lock = threading.Lock()
_embeddings: Embeddings | None = None

_NO_HITS_MSG = "未检索到足够相关的知识片段。"


def _rag_max_distance() -> float:
    raw = os.getenv("RAG_MAX_DISTANCE", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return RAG_MAX_DISTANCE


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = get_rag_embedding_model()
    return _embeddings


def get_store() -> Chroma | None:
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


def warmup() -> None:
    _get_embeddings()
    get_store()


def _where(corpus: str) -> dict:
    return {"corpus": corpus}


def _passes_distance_threshold(distance: float, *, max_distance: float) -> bool:
    """Chroma 返回的为距离，越小越相似（cosine 空间下 0=完全一致）。"""
    return distance <= max_distance


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
    max_distance: float | None = None,
) -> list[tuple[Document, float]]:
    """向量召回，返回 (Document, distance)；distance 越小越相似。"""
    q = (query or "").strip()
    if not q:
        return []

    if corpus not in get_domains():
        return []

    store = get_store()
    if store is None:
        return []

    cutoff = _rag_max_distance() if max_distance is None else max_distance
    pairs = store.similarity_search_with_score(q, k=top_k, filter=_where(corpus))
    return [(doc, float(score)) for doc, score in pairs if _passes_distance_threshold(float(score), max_distance=cutoff)]


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
) -> str:
    """多问句粗召回 → 去重合并 → DashScope 精排 → 格式化注入上下文。"""
    from common.rerank import rerank_documents

    qs = [q.strip() for q in questions if (q or "").strip()]
    if not qs:
        return "检索关键词为空。"

    if corpus not in get_domains():
        return f"未知 corpus={corpus!r}"

    if get_store() is None:
        return (
            f"向量库未构建：{chroma_path()}。"
            "请在 backend_langchain 下运行：python Scripts/build_rag_knowledge.py"
        )

    k_recall = RECALL_K if recall_k is None else recall_k
    batches = [search_hits(q, corpus=corpus, top_k=k_recall) for q in qs]
    merged = _merge_hits(batches)
    if not merged:
        return _NO_HITS_MSG

    ranked = rerank_documents(qs[0], merged, top_k=rerank_top_k)
    if not ranked:
        return _NO_HITS_MSG
    return format_hits(ranked)


# 兼容旧 import 路径
__all__ = [
    "COLLECTION",
    "CORPUS_AGENT",
    "CORPUS_INTERVIEW",
    "chroma_path",
    "format_hits",
    "get_store",
    "retrieve_context",
    "search_hits",
    "warmup",
]
