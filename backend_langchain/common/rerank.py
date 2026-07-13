"""精排：DashScope qwen3-rerank API，返回 top_k 文档。"""
from __future__ import annotations

import logging
import os

from langchain_core.documents import Document

from backend_langchain.logger_func import log_info_event, log_warning_event
from config.config import RERANK_TOP_K, dashscope_api_key, dashscope_rerank_model

logger = logging.getLogger(__name__)

_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
_DOC_PREVIEW_CHARS = 1200


def _rerank_enabled() -> bool:
    raw = os.getenv("RERANK_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _doc_key(doc: Document) -> str:
    meta = doc.metadata or {}
    sp = str(meta.get("source_path") or "")
    body = (doc.page_content or "").strip()
    return f"{sp}\n{body[:200]}"


def _fallback_by_distance(
    hits: list[tuple[Document, float]], *, top_k: int
) -> list[Document]:
    ordered = sorted(hits, key=lambda x: x[1])
    return [doc for doc, _ in ordered[:top_k]]


def _dashscope_rerank(query: str, documents: list[str], *, top_n: int) -> list[int]:
    import httpx

    api_key = dashscope_api_key()
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")

    model = dashscope_rerank_model()
    payload: dict = {
        "model": model,
        "input": {"query": query, "documents": documents},
        "parameters": {"top_n": top_n, "return_documents": False},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(_RERANK_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    output = data.get("output") or {}
    results = output.get("results") or []
    indices: list[int] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        if isinstance(idx, int) and 0 <= idx < len(documents):
            indices.append(idx)
    return indices


def rerank_documents(
    query: str,
    hits: list[tuple[Document, float]],
    *,
    top_k: int | None = None,
) -> list[Document]:
    """对粗召回结果精排；失败或未启用时按向量 distance 取 top_k。"""
    k = RERANK_TOP_K if top_k is None else max(1, top_k)
    if not hits:
        return []
    if not _rerank_enabled() or not dashscope_api_key():
        return _fallback_by_distance(hits, top_k=k)

    q = (query or "").strip()
    if not q:
        return _fallback_by_distance(hits, top_k=k)

    docs = [doc for doc, _ in hits]
    previews = [(doc.page_content or "").strip()[:_DOC_PREVIEW_CHARS] for doc in docs]
    previews = [p if p else " " for p in previews]

    try:
        ranked_idx = _dashscope_rerank(q, previews, top_n=min(k, len(previews)))
        if not ranked_idx:
            return _fallback_by_distance(hits, top_k=k)
        log_info_event(logger, "rerank_ok", model=dashscope_rerank_model(), top_k=k)
        return [docs[i] for i in ranked_idx[:k]]
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "rerank_failed", error=str(e))
        return _fallback_by_distance(hits, top_k=k)
