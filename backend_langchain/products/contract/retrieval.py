"""Owner-scoped hybrid retrieval: pgvector + actual BM25 + RRF + model rerank."""

import asyncio
import math
import os
import re
import httpx
from openai import APIError
from collections import Counter, defaultdict

from sqlalchemy import func, select
from common.config.config import dashscope_model_name, dashscope_rerank_model
from common.integrations.retrieval_models import (
    make_dashscope_embeddings,
    rerank_indices,
)
from products.contract.models import (
    ContractKnowledgeChunkModel as Chunk,
    ContractKnowledgeDocumentModel as Document,
)

EMBEDDING_DIMENSIONS = 1024


def settings():
    def integer(name, default, low, high):
        value = int(os.getenv("CONTRACT_RAG_" + name, default))
        if not low <= value <= high:
            raise ValueError(f"CONTRACT_RAG_{name} 超出允许范围")
        return value

    return dict(
        top_k=integer("TOP_K", 3, 1, 8),
        recall_k=integer("RECALL_K", 24, 1, 100),
        rerank_count=integer("RERANK_COUNT", 16, 1, 100),
        timeout=integer("TIMEOUT", 30, 1, 120),
        bm25_max_chunks=integer("BM25_MAX_CHUNKS", 10000, 1, 50000),
    )


def tokenize(text: str) -> list[str]:
    terms = []
    for token in re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]+", text.casefold()):
        if re.match(r"[a-z0-9_]", token):
            terms.append(token)
        else:
            terms.extend(token)
            terms.extend(token[i : i + 2] for i in range(len(token) - 1))
    return terms


def bm25_scores(
    query: str, tokenized: list[list[str]], *, k1=1.5, b=0.75
) -> list[float]:
    """Okapi BM25 with positive log IDF; this is not PostgreSQL FTS."""
    if not tokenized:
        return []
    terms = set(tokenize(query))
    counts = [Counter(tokens) for tokens in tokenized]
    dfs = Counter(term for counts_in_doc in counts for term in counts_in_doc)
    average = sum(map(len, tokenized)) / len(tokenized) or 1
    scores = []
    for tokens, frequencies in zip(tokenized, counts):
        score = 0.0
        for term in terms:
            frequency = frequencies[term]
            if frequency:
                idf = math.log(
                    1 + (len(tokenized) - dfs[term] + 0.5) / (dfs[term] + 0.5)
                )
                score += (
                    idf
                    * frequency
                    * (k1 + 1)
                    / (frequency + k1 * (1 - b + b * len(tokens) / average))
                )
        scores.append(score)
    return scores


def rrf(*rankings, constant=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), 1):
            scores[key] += 1 / (constant + rank)
    return sorted(scores, key=lambda key: (-scores[key], str(key)))


def validate_vectors(vectors, expected_count):
    if len(vectors) != expected_count:
        raise ValueError("Embedding 数量与 Chunk 不一致")
    for vector in vectors:
        if (
            len(vector) != EMBEDDING_DIMENSIONS
            or not all(math.isfinite(float(v)) for v in vector)
            or sum(float(v) ** 2 for v in vector) == 0
        ):
            raise ValueError("Embedding 维度、数值或零向量非法，请检查模型配置")
    return [[float(value) for value in vector] for vector in vectors]


def scoped_chunks(owner_id):
    if not isinstance(owner_id, int) or owner_id <= 0:
        raise ValueError("知识库检索必须明确用户权限范围")
    return (
        select(Chunk, Document)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.user_id == owner_id,
            Document.user_id == owner_id,
            Document.status == "ready",
            Chunk.generation == Document.generation,
            Chunk.document_version == Document.document_version,
            Chunk.embedding_model == Document.embedding_model,
        )
    )


def reference_snapshot(chunk, document):
    return dict(
        chunk_id=str(chunk.id),
        document_id=str(document.id),
        document_version=chunk.document_version,
        index_generation=chunk.generation,
        owner_id=document.user_id,
        filename=document.filename,
        document_type=document.category,
        chunk_text=chunk.chunk_text,
        locator=chunk.locator,
        embedding_model=chunk.embedding_model,
    )


def clause_query(targets, *, party_role="", contract_type=""):
    parts = [f'我方角色:{party_role or "未指定"} 合同类型:{contract_type or "未指定"}']
    for clause in targets:
        parts.append(
            f'{clause["clause_type"]} {clause["title"]}\n{clause["original_text"][:900]}'
        )
    return "\n".join(parts)[:8000]


async def retrieve_references(
    factory,
    owner_id: int,
    query: str,
    *,
    embeddings=None,
    reranker=None,
    config=None,
    diagnostics=None,
):
    config = config or settings()

    async def retrieve():
        model_name = dashscope_model_name()
        # Both branches are restricted BEFORE search. No all-tenant result filtering.
        async with factory() as session, session.begin():
            statement = scoped_chunks(owner_id)
            count = await session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            if count > config["bm25_max_chunks"]:
                raise ValueError(
                    "私有知识库超过轻量 BM25 容量，请接入 Elasticsearch 后再审查"
                )
            rows = (await session.execute(statement)).all()
            corpus = {c.id: reference_snapshot(c, d) for c, d in rows}
            tokens = {c.id: c.token_index for c, _ in rows}
            sqlite_vectors = (
                {c.id: list(c.embedding) for c, _ in rows}
                if session.bind.dialect.name == "sqlite"
                else {}
            )
        if not corpus:
            return []
        if any(item["embedding_model"] != model_name for item in corpus.values()):
            raise ValueError("知识库 Embedding 模型已变化，请重新索引文档")
        embedding_model = embeddings or make_dashscope_embeddings(
            dimensions=EMBEDDING_DIMENSIONS, timeout=config["timeout"], max_retries=0
        )
        vector = validate_vectors(
            [await asyncio.to_thread(embedding_model.embed_query, query)], 1
        )[0]
        async with factory() as session, session.begin():
            if session.bind.dialect.name == "postgresql":
                distance = Chunk.embedding.cosine_distance(vector)
                dense = (
                    await session.scalars(
                        scoped_chunks(owner_id)
                        .with_only_columns(Chunk.id)
                        .order_by(distance, Chunk.id)
                        .limit(config["recall_k"])
                    )
                ).all()
            else:
                # SQLite is test-only; production uses the actual pgvector operator/index.
                def similarity(key):
                    candidate = sqlite_vectors[key]
                    norm = math.sqrt(
                        sum(x * x for x in candidate) * sum(x * x for x in vector)
                    )
                    return (
                        sum(a * b for a, b in zip(candidate, vector)) / norm
                        if norm
                        else -1
                    )

                dense = sorted(corpus, key=lambda key: (-similarity(key), str(key)))[
                    : config["recall_k"]
                ]
        dense = [key for key in dense if key in corpus]
        scores = bm25_scores(query, list(tokens.values()))
        bm25 = [
            key
            for key, score in sorted(
                zip(tokens, scores), key=lambda pair: (-pair[1], str(pair[0]))
            )
            if score > 0
        ][: config["recall_k"]]
        fused = rrf(dense, bm25)[: config["rerank_count"]]
        if not fused:
            return []
        texts = [corpus[key]["chunk_text"] for key in fused]
        rank = reranker or rerank_indices
        indices = await asyncio.to_thread(
            rank, query, texts, top_n=config["top_k"], timeout=config["timeout"]
        )
        if (
            not indices
            or len(set(indices)) != len(indices)
            or any(
                not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(fused)
                for i in indices
            )
        ):
            raise ValueError("知识库 Rerank 未返回有效结果")
        chosen = [corpus[fused[i]] for i in indices[: config["top_k"]]]
        # Deletion/reindex during a model call cannot publish a stale current reference.
        async with factory() as session, session.begin():
            current = (
                await session.execute(
                    scoped_chunks(owner_id).where(
                        Chunk.id.in_([fused[i] for i in indices])
                    )
                )
            ).all()
            valid_ids = {str(c.id) for c, _ in current}
        available = [item for item in chosen if item["chunk_id"] in valid_ids]
        if diagnostics is not None and len(available) != len(chosen):
            diagnostics["unavailable_count"] = len(chosen) - len(available)
        return available  # Withdrawn sources are omitted, never fabricated or cited.

    try:
        return await asyncio.wait_for(retrieve(), timeout=config["timeout"])
    except TimeoutError as exc:
        raise ValueError("知识库检索超时，请稍后重新分析") from exc
    except (httpx.HTTPError, APIError, RuntimeError) as exc:
        raise ValueError(
            "知识库 Embedding / Rerank 服务不可用，请检查模型配置"
        ) from exc
