from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from langchain_core.documents import Document


class EmbeddingPort(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class RerankerPort(Protocol):
    def rerank(
        self, query: str, documents: Sequence[tuple[Document, float]], *, top_k: int | None = None
    ) -> list[tuple[Document, float]]: ...


class VectorStorePort(Protocol):
    def add(self, documents: list[Document]) -> int: ...

    def similarity_search_with_score(
        self, query: str, *, k: int, scope: str, user_id: int | None = None
    ) -> list[tuple[Document, float]]: ...


class RetrievalPort(Protocol):
    def retrieve(
        self, questions: list[str], *, scope: str, user_id: int | None = None
    ) -> str: ...
