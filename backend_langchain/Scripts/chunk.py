"""文档切分：加载、清洗后切 chunk，以及增量去重用的 source_path 查询。"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from file_cleanup import clean_markdown_text, clean_pdf_text
from config.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

_CHROMA_PAGE = 5000
_H2 = re.compile(r"^##\s")
_H3 = re.compile(r"^###\s")


def rag_metadata(*, corpus: str, domain: str, source_path: str) -> dict[str, str]:
    return {"corpus": corpus, "domain": domain, "source_path": source_path}


def existing_source_paths(chroma_dir: Path, *, collection: str) -> set[str]:
    """库内已有文件的 source_path（增量建库时跳过）。"""
    if not chroma_dir.is_dir():
        return set()
    probe = Chroma(
        persist_directory=str(chroma_dir),
        embedding_function=None,
        collection_name=collection,
    )
    out: set[str] = set()
    offset = 0
    while True:
        batch = probe.get(include=["metadatas"], limit=_CHROMA_PAGE, offset=offset)
        metas = batch.get("metadatas") or []
        if not metas:
            break
        for m in metas:
            if m and (sp := m.get("source_path")):
                out.add(str(sp))
        if len(metas) < _CHROMA_PAGE:
            break
        offset += _CHROMA_PAGE
    return out


def _split_by_header(text: str, pattern: re.Pattern[str]) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if pattern.match(line):
            if buf:
                block = "\n".join(buf).strip()
                if block:
                    parts.append(block)
            buf = [line]
        else:
            buf.append(line)
    if buf:
        block = "\n".join(buf).strip()
        if block:
            parts.append(block)
    return parts


def _parent_h2_line(block: str) -> str:
    first = (block.splitlines() or [""])[0]
    return first if _H2.match(first) else ""


def _maybe_split_preamble(block: str, *, max_len: int) -> list[str]:
    """首个 ## 之前的导语：过长则按段切开，避免整块抢相似度。"""
    if not block or _H2.match((block.splitlines() or [""])[0]):
        return [block] if block else []
    if len(block) <= max_len:
        return [block]
    paras = [p.strip() for p in re.split(r"\n{2,}", block) if p.strip()]
    if len(paras) <= 1:
        return [block]
    out: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in paras:
        plen = len(para)
        if buf and buf_len + plen + 2 > max_len:
            out.append("\n\n".join(buf))
            buf, buf_len = [], 0
        buf.append(para)
        buf_len += plen + 2
    if buf:
        out.append("\n\n".join(buf))
    return out


def _markdown_sections(text: str, *, chunk_size: int) -> list[str]:
    """先 ## 再 ###（### 始终独立）；导语过长再按段拆。"""
    text = (text or "").strip()
    if not text:
        return []

    preamble_max = max(200, chunk_size // 2)
    blocks = _split_by_header(text, _H2)
    if len(blocks) <= 1:
        subs = _split_by_header(text, _H3)
        blocks = subs if len(subs) > 1 else [text]

    out: list[str] = []
    for i, block in enumerate(blocks):
        if i == 0 and not _H2.match((block.splitlines() or [""])[0]):
            out.extend(_maybe_split_preamble(block, max_len=preamble_max))
            continue

        subs = _split_by_header(block, _H3)
        if len(subs) > 1:
            parent = _parent_h2_line(block)
            for sub in subs:
                if sub.startswith("###") and parent:
                    sub = f"{parent}\n\n{sub}"
                out.append(sub)
        elif len(block) <= chunk_size:
            out.append(block)
        else:
            out.append(block)
    return out


def split_documents(
    docs: list[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    drop_empty: bool = False,
    markdown_aware: bool = False,
) -> list[Document]:
    if not docs:
        return []
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: list[Document] = []
    for doc in docs:
        meta = dict(doc.metadata or {})
        if markdown_aware:
            sections = _markdown_sections(doc.page_content or "", chunk_size=chunk_size)
            for section in sections:
                if len(section) <= chunk_size:
                    chunks.append(Document(page_content=section, metadata=meta))
                else:
                    chunks.extend(splitter.split_documents([Document(page_content=section, metadata=meta)]))
        else:
            chunks.extend(splitter.split_documents([doc]))
    if drop_empty:
        chunks = [c for c in chunks if (c.page_content or "").strip()]
    return chunks


def load_markdown_documents(
    paths: list[Path],
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
    strip_images: bool = True,
) -> list[Document]:
    out: list[Document] = []
    for path in paths:
        sp = path.relative_to(knowledge_root).as_posix()
        raw = path.read_text(encoding="utf-8")
        body = clean_markdown_text(raw, strip_images=strip_images)
        if not body:
            continue
        out.append(
            Document(
                page_content=body,
                metadata=rag_metadata(corpus=corpus, domain=domain, source_path=sp),
            )
        )
    return out


def load_pdf_documents(
    pdf_path: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
) -> list[Document]:
    sp = pdf_path.relative_to(knowledge_root).as_posix()
    out: list[Document] = []
    for page in PyPDFLoader(str(pdf_path)).load():
        text = clean_pdf_text(page.page_content or "")
        if text:
            out.append(
                Document(page_content=text, metadata=rag_metadata(corpus=corpus, domain=domain, source_path=sp))
            )
    return out


def agent_markdown_chunks(
    domain_dir: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
    skip_sources: set[str] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    strip_images: bool = True,
) -> list[Document]:
    paths = sorted(domain_dir.rglob("*.md"))
    if skip_sources:
        paths = [p for p in paths if p.relative_to(knowledge_root).as_posix() not in skip_sources]
    if not paths:
        return []
    return split_documents(
        load_markdown_documents(
            paths, knowledge_root, corpus=corpus, domain=domain, strip_images=strip_images
        ),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        markdown_aware=True,
    )


def interview_pdf_chunks(
    pdf_path: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    raw = load_pdf_documents(pdf_path, knowledge_root, corpus=corpus, domain=domain)
    if not raw:
        raise RuntimeError(f"无可用文本：{pdf_path.name}")
    chunks = split_documents(raw, chunk_size=chunk_size, chunk_overlap=chunk_overlap, drop_empty=True)
    if not chunks:
        raise RuntimeError(f"切分后无有效块：{pdf_path.name}")
    return chunks
