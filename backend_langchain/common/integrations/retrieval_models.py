"""Shared model transport only; no product data, retrieval policy, or fallback."""

import math
import httpx
from common.config.config import (
    DASHSCOPE_EMBEDDING_BASE_URL,
    dashscope_api_key,
    dashscope_model_name,
    dashscope_dimensions,
    dashscope_embedding_batch_size,
    dashscope_rerank_model,
)

RERANK_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


def make_dashscope_embeddings(
    *, dimensions=None, timeout=None, api_key=None, model=None, max_retries=2
):
    from langchain_openai import OpenAIEmbeddings

    key = dashscope_api_key() if api_key is None else api_key
    if not key:
        raise RuntimeError("未配置 DashScope Embedding API Key")
    name = model or dashscope_model_name()
    kwargs = dict(
        model=name,
        api_key=key,
        base_url=DASHSCOPE_EMBEDDING_BASE_URL,
        check_embedding_ctx_length=False,
        chunk_size=min(10, dashscope_embedding_batch_size()),
        request_timeout=timeout,
        max_retries=max_retries,
    )
    if name in ("text-embedding-v3", "text-embedding-v4"):
        kwargs["dimensions"] = (
            dimensions if dimensions is not None else dashscope_dimensions()
        )
    return OpenAIEmbeddings(**kwargs)


def rerank_indices(
    query: str, documents: list[str], *, top_n: int, timeout=30
) -> list[int]:
    if not documents:
        return []
    key = dashscope_api_key()
    if not key:
        raise RuntimeError("未配置 DashScope Rerank API Key")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            RERANK_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": dashscope_rerank_model(),
                "input": {"query": query, "documents": documents},
                "parameters": {
                    "top_n": min(top_n, len(documents)),
                    "return_documents": False,
                },
            },
        )
        response.raise_for_status()
        rows = response.json().get("output", {}).get("results", [])
    indices = []
    for row in rows:
        index, score = row.get("index"), row.get("relevance_score")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(documents)
            or index in indices
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
        ):
            raise ValueError("Rerank 返回非法索引或评分")
        indices.append(index)
    if not indices:
        raise ValueError("Rerank 未返回有效结果")
    return indices[:top_n]
