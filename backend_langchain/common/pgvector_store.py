"""pgvector 向量库：单表 rag_embeddings，按 corpus/user_id 过滤（替代 Chroma）。

- 同步实现（psycopg3），供 RAG 检索 / 建库 / 上传入库调用（均在线程池中执行）。
- 距离用 cosine（`<=>`），返回 distance 越小越相似，后续交给 rerank 精排。
- 向量以文本字面量 `[...]::vector` 传参，无需注册 psycopg 适配器。
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

_TABLE = "rag_embeddings"


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class PgVectorStore:
    """单表向量库，corpus 区分内置知识库 / 用户上传库。"""

    def __init__(self, embeddings: Embeddings, *, dim: int, dsn: str) -> None:
        self._emb = embeddings
        self._dim = int(dim)
        self._dsn = dsn
        self._ready = False
        self._lock = threading.Lock()

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def setup(self) -> None:
        """建扩展 / 表 / 索引（幂等）。"""
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            with self._connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {_TABLE} (
                        id BIGSERIAL PRIMARY KEY,
                        corpus TEXT NOT NULL,
                        domain TEXT,
                        user_id TEXT,
                        document_id TEXT,
                        source_path TEXT,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({self._dim}) NOT NULL
                    )
                    """
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_corpus ON {_TABLE} (corpus)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_user ON {_TABLE} (user_id)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_doc ON {_TABLE} (document_id)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_embedding "
                    f"ON {_TABLE} USING hnsw (embedding vector_cosine_ops)"
                )
            self._ready = True

    def add(self, documents: list[Document]) -> int:
        """嵌入并写入；metadata 中的 corpus/domain/user_id/document_id/source_path 提列存储。"""
        self.setup()
        docs = [d for d in documents if (d.page_content or "").strip()]
        if not docs:
            return 0

        vectors = self._emb.embed_documents([d.page_content for d in docs])
        rows: list[tuple[Any, ...]] = []
        for doc, vec in zip(docs, vectors):
            meta = dict(doc.metadata or {})
            uid = meta.get("user_id")
            did = meta.get("document_id")
            rows.append(
                (
                    str(meta.get("corpus") or ""),
                    meta.get("domain"),
                    (str(uid) if uid is not None else None),
                    (str(did) if did is not None else None),
                    meta.get("source_path"),
                    doc.page_content,
                    json.dumps(meta, ensure_ascii=False),
                    _vec_literal(vec),
                )
            )

        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO {_TABLE} "
                f"(corpus, domain, user_id, document_id, source_path, content, metadata, embedding) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)",
                rows,
            )
        return len(rows)

    def similarity_search_with_score(
        self,
        query: str,
        *,
        k: int,
        corpus: str,
        user_id: int | None = None,
    ) -> list[tuple[Document, float]]:
        self.setup()
        q = (query or "").strip()
        if not q:
            return []

        qvec = _vec_literal(self._emb.embed_query(q))
        where = ["corpus = %s"]
        tail: list[Any] = [corpus]
        if user_id is not None:
            where.append("user_id = %s")
            tail.append(str(user_id))

        sql = (
            f"SELECT content, metadata, embedding <=> %s::vector AS distance "
            f"FROM {_TABLE} WHERE {' AND '.join(where)} "
            f"ORDER BY distance ASC LIMIT %s"
        )
        params = [qvec, *tail, int(k)]

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        out: list[tuple[Document, float]] = []
        for content, meta, dist in rows:
            md = meta if isinstance(meta, dict) else (json.loads(meta) if meta else {})
            out.append((Document(page_content=content, metadata=md), float(dist)))
        return out

    def list_source_paths(self, *, corpus: str, user_id: int | None = None) -> set[str]:
        self.setup()
        where = ["corpus = %s", "source_path IS NOT NULL"]
        params: list[Any] = [corpus]
        if user_id is not None:
            where.append("user_id = %s")
            params.append(str(user_id))
        sql = f"SELECT DISTINCT source_path FROM {_TABLE} WHERE {' AND '.join(where)}"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return {r[0] for r in cur.fetchall() if r[0]}

    def delete_by_document_id(self, document_id: int) -> int:
        self.setup()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {_TABLE} WHERE document_id = %s", (str(document_id),))
            return cur.rowcount

    def clear_corpus(self, corpus: str) -> int:
        self.setup()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {_TABLE} WHERE corpus = %s", (corpus,))
            return cur.rowcount

    def count(self, *, corpus: str | None = None, user_id: int | None = None) -> int:
        self.setup()
        where: list[str] = []
        params: list[Any] = []
        if corpus is not None:
            where.append("corpus = %s")
            params.append(corpus)
        if user_id is not None:
            where.append("user_id = %s")
            params.append(str(user_id))
        sql = f"SELECT COUNT(*) FROM {_TABLE}"
        if where:
            sql += f" WHERE {' AND '.join(where)}"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0
