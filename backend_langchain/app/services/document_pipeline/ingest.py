"""按文件格式分流：加载 → 清洗 → 切块（建库与预览共用）。"""
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from app.services.document_pipeline.chunk import (
    load_markdown_documents,
    load_pdf_documents,
    load_plain_text_documents,
    merge_small_chunks,
    split_documents,
    split_pdf_documents,
)
from config.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

_FORMAT_BY_SUFFIX = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
    ".txt": "text",
    ".json": "text",
}


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _FORMAT_BY_SUFFIX:
        return _FORMAT_BY_SUFFIX[ext]
    if path.name.lower() == "requirements.txt":
        return "text"
    return "text"


def load_documents_for_path(
    path: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
    fmt: str | None = None,
) -> list[Document]:
    kind = fmt or detect_format(path)
    if kind == "markdown":
        return load_markdown_documents(
            [path], knowledge_root, corpus=corpus, domain=domain, strip_images=True
        )
    if kind == "pdf":
        return load_pdf_documents(path, knowledge_root, corpus=corpus, domain=domain)
    return load_plain_text_documents(path, knowledge_root, corpus=corpus, domain=domain)


def chunks_from_path(
    path: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
    fmt: str | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    kind = fmt or detect_format(path)
    docs = load_documents_for_path(
        path, knowledge_root, corpus=corpus, domain=domain, fmt=kind
    )
    if not docs:
        return []
    if kind == "markdown":
        chunks = split_documents(
            docs,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            markdown_aware=True,
            drop_empty=True,
        )
        return merge_small_chunks(chunks)
    if kind == "pdf":
        return split_pdf_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = split_documents(
        docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        markdown_aware=False,
        drop_empty=True,
    )
    return merge_small_chunks(chunks)
