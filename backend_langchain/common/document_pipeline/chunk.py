"""文档切分：加载、清洗后切 chunk。"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.document_pipeline.cleanup import (
    clean_markdown_text,
    clean_pdf_text,
    clean_plain_text,
    split_pdf_text_by_questions,
)
from common.document_pipeline.pdf import extract_pdf_pages
from config.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

_H2 = re.compile(r"^##\s")
_H3 = re.compile(r"^###\s")
_MIN_CHUNK_CHARS = 80
_PREAMBLE_MERGE_CHARS = 200


def rag_metadata(*, corpus: str, domain: str, source_path: str) -> dict[str, str]:
    return {"corpus": corpus, "domain": domain, "source_path": source_path}


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
            for i, sub in enumerate(subs):
                if sub.startswith("###") and parent:
                    prior = "\n\n".join(subs[:i])
                    if parent.strip() not in prior:
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


def _is_small_chunk(text: str, *, min_chars: int) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if len(t) < min_chars:
        return True
    first = (t.splitlines() or [""])[0]
    if len(t) < _PREAMBLE_MERGE_CHARS and not _H2.match(first) and not first.startswith("###"):
        return True
    return False


def merge_small_chunks(
    chunks: list[Document],
    *,
    min_chars: int = _MIN_CHUNK_CHARS,
) -> list[Document]:
    """过短块并入相邻块，减少孤儿 chunk。"""
    if not chunks:
        return []
    merged: list[Document] = []
    carry: Document | None = None

    for ch in chunks:
        text = (ch.page_content or "").strip()
        if not text:
            continue
        if carry is None:
            carry = ch
            continue
        if _is_small_chunk(carry.page_content or "", min_chars=min_chars):
            carry = Document(
                page_content=f"{carry.page_content}\n\n{text}".strip(),
                metadata=dict(carry.metadata or {}),
            )
        else:
            merged.append(carry)
            carry = ch

    if carry is not None:
        if merged and _is_small_chunk(carry.page_content or "", min_chars=min_chars):
            prev = merged[-1]
            merged[-1] = Document(
                page_content=f"{prev.page_content}\n\n{carry.page_content}".strip(),
                metadata=dict(prev.metadata or {}),
            )
        else:
            merged.append(carry)
    return merged


def split_pdf_documents(
    docs: list[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """PDF：先按问句行切，再对过长块做字符切分。"""
    if not docs:
        return []
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: list[Document] = []
    for doc in docs:
        meta = dict(doc.metadata or {})
        for section in split_pdf_text_by_questions(doc.page_content or ""):
            if len(section) <= chunk_size:
                chunks.append(Document(page_content=section, metadata=meta))
            else:
                chunks.extend(
                    splitter.split_documents([Document(page_content=section, metadata=meta)])
                )
    chunks = [c for c in chunks if (c.page_content or "").strip()]
    return merge_small_chunks(chunks)


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
    parts: list[str] = []
    for _page_num, raw in extract_pdf_pages(pdf_path):
        text = clean_pdf_text(raw)
        if text:
            parts.append(text)
    if not parts:
        return []
    return [
        Document(
            page_content="\n\n".join(parts),
            metadata=rag_metadata(corpus=corpus, domain=domain, source_path=sp),
        )
    ]


def load_plain_text_documents(
    path: Path,
    knowledge_root: Path,
    *,
    corpus: str,
    domain: str,
) -> list[Document]:
    try:
        sp = path.resolve().relative_to(knowledge_root.resolve()).as_posix()
    except ValueError:
        sp = path.name
    body = clean_plain_text(path.read_text(encoding="utf-8", errors="replace"))
    if not body:
        return []
    return [
        Document(
            page_content=body,
            metadata=rag_metadata(corpus=corpus, domain=domain, source_path=sp),
        )
    ]


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
    chunks = split_documents(
        load_markdown_documents(
            paths, knowledge_root, corpus=corpus, domain=domain, strip_images=strip_images
        ),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        markdown_aware=True,
        drop_empty=True,
    )
    return merge_small_chunks(chunks)


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
    chunks = split_pdf_documents(raw, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise RuntimeError(f"切分后无有效块：{pdf_path.name}")
    return chunks
