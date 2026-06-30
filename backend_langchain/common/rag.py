"""统一 Chroma RAG：单 collection，corpus + domain metadata 隔离。"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from common.embedding import get_embedding_model
from config.config import (
    COLLECTION,
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    DEFAULT_HF_MODEL,
    HF_EMBEDDING_BATCH_SIZE,
    TOP_K,
    chroma_path,
    get_domains,
)

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_store: Chroma | None = None
_store_lock = threading.Lock()
_embeddings: Embeddings | None = None


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = get_embedding_model(
            DEFAULT_HF_MODEL,
            device="cpu",
            normalize_embeddings=True,
            batch_size=HF_EMBEDDING_BATCH_SIZE,
        )
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


def _where(corpus: str, domain: str | None) -> dict:
    if domain:
        return {"$and": [{"corpus": corpus}, {"domain": domain}]}
    return {"corpus": corpus}


def format_hits(docs: list[Document]) -> str:
    if not docs:
        return "未检索到相关知识片段。"
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        sp = (meta.get("source_path") or "").strip()
        title = Path(sp).name if sp else ""
        head = f"[{i}] {title}".strip()
        body = (doc.page_content or "").strip()[:1500]
        parts.append(f"{head}\n{body}")
    return "\n\n".join(parts)


def search(
    query: str,
    *,
    corpus: str,
    domain: str | None = None,
    top_k: int = TOP_K,
) -> str:
    q = (query or "").strip()
    if not q:
        return "检索关键词为空。"

    domains = get_domains()
    if corpus not in domains:
        return f"未知 corpus={corpus!r}"

    allowed = domains[corpus]
    if domain and domain not in allowed:
        hint = ", ".join(sorted(allowed)) if allowed else "（暂无域目录）"
        return f"未知 domain={domain!r}，可选：{hint}"

    store = get_store()
    if store is None:
        return (
            f"向量库未构建：{chroma_path()}。"
            "请在 backend_langchain 下运行：python Scripts/build_rag_knowledge.py"
        )

    return format_hits(store.similarity_search(q, k=top_k, filter=_where(corpus, domain)))

# 兼容旧 import 路径
__all__ = [
    "COLLECTION",
    "CORPUS_AGENT",
    "CORPUS_INTERVIEW",
    "chroma_path",
    "format_hits",
    "get_store",
    "search",
    "warmup",
]
