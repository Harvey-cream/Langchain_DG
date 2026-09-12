"""长期记忆表 memories（pgvector），与 rag_embeddings 隔离。"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from langchain_core.embeddings import Embeddings

_TABLE = "memories"


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


@dataclass(frozen=True)
class MemoryRow:
    id: int
    user_id: int
    memory_key: str
    memory_type: str
    content: str
    importance: float
    distance: float | None = None


class LongTermMemoryStore:
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
                        user_id INTEGER NOT NULL,
                        memory_key TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        importance REAL NOT NULL DEFAULT 0.5,
                        embedding vector({self._dim}) NOT NULL,
                        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
                        is_active BOOLEAN NOT NULL DEFAULT true
                    )
                    """
                )
                conn.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS uq_{_TABLE}_user_key_active "
                    f"ON {_TABLE} (user_id, memory_key) WHERE is_active"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_user_active "
                    f"ON {_TABLE} (user_id) WHERE is_active"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{_TABLE}_embedding "
                    f"ON {_TABLE} USING hnsw (embedding vector_cosine_ops)"
                )
            self._ready = True

    def search(
        self,
        query: str,
        *,
        user_id: int,
        k: int = 5,
    ) -> list[MemoryRow]:
        self.setup()
        q = (query or "").strip()
        if not q:
            return []
        qvec = _vec_literal(self._emb.embed_query(q))
        sql = (
            f"SELECT id, user_id, memory_key, memory_type, content, importance, "
            f"embedding <=> %s::vector AS distance "
            f"FROM {_TABLE} WHERE user_id = %s AND is_active "
            f"ORDER BY distance ASC LIMIT %s"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (qvec, int(user_id), int(k)))
            rows = cur.fetchall()
        return [
            MemoryRow(
                id=int(r[0]),
                user_id=int(r[1]),
                memory_key=str(r[2]),
                memory_type=str(r[3]),
                content=str(r[4]),
                importance=float(r[5]),
                distance=float(r[6]) if r[6] is not None else None,
            )
            for r in rows
        ]

    def get_active(self, user_id: int, memory_key: str) -> MemoryRow | None:
        self.setup()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id, user_id, memory_key, memory_type, content, importance "
                f"FROM {_TABLE} WHERE user_id = %s AND memory_key = %s AND is_active "
                f"LIMIT 1",
                (int(user_id), memory_key),
            )
            r = cur.fetchone()
        if not r:
            return None
        return MemoryRow(
            id=int(r[0]),
            user_id=int(r[1]),
            memory_key=str(r[2]),
            memory_type=str(r[3]),
            content=str(r[4]),
            importance=float(r[5]),
        )

    def upsert(
        self,
        *,
        user_id: int,
        memory_key: str,
        memory_type: str,
        content: str,
        importance: float,
    ) -> str:
        """Insert or update active row. Returns 'insert' | 'update'."""
        self.setup()
        text = (content or "").strip()
        if not text:
            return "ignore"
        key = (memory_key or "").strip()
        if not key:
            return "ignore"
        vec = _vec_literal(self._emb.embed_documents([text])[0])
        imp = max(0.0, min(1.0, float(importance)))
        mtype = (memory_type or "fact").strip() or "fact"
        existing = self.get_active(user_id, key)
        with self._connect() as conn, conn.cursor() as cur:
            if existing:
                cur.execute(
                    f"UPDATE {_TABLE} SET memory_type = %s, content = %s, importance = %s, "
                    f"embedding = %s::vector, updated_at = (NOW() AT TIME ZONE 'UTC') "
                    f"WHERE id = %s",
                    (mtype, text, imp, vec, existing.id),
                )
                return "update"
            cur.execute(
                f"INSERT INTO {_TABLE} "
                f"(user_id, memory_key, memory_type, content, importance, embedding) "
                f"VALUES (%s, %s, %s, %s, %s, %s::vector)",
                (int(user_id), key, mtype, text, imp, vec),
            )
            return "insert"


_store: LongTermMemoryStore | None = None
_store_lock = threading.Lock()


def get_long_term_store() -> LongTermMemoryStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        from infrastructure.rag.embedding import get_rag_embedding_model
        from app.settings import VECTOR_POSTGRES_URL
        from config.config import dashscope_dimensions

        _store = LongTermMemoryStore(
            get_rag_embedding_model(),
            dim=dashscope_dimensions(),
            dsn=VECTOR_POSTGRES_URL,
        )
        return _store
