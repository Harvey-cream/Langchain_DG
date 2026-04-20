"""
将 docs2 下指定 PDF 按「题库分区」写入 Chroma：每个 PDF 对应 chroma_db1 下的独立子目录（独立向量库）。

默认分区（PDF 文件名 → persist 子目录名，均在 Langchain_knowledge/chroma_db1/ 下）：
  - AI大模型…pdf  → AI大模型原理和应用面试题
  - Java…pdf      → Java 热门面试题
  - Vue…pdf       → 前端Vue 基础面试题速

解析仅文本（PyPDF），不含页面图片；正文做轻量去图片标记清洗。

请在启动本脚本前在 shell 中设置 HF_ENDPOINT（或 .env），否则将走 huggingface.co。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG_RE = re.compile(r"<img\s+[^>]*>", flags=re.IGNORECASE)
_NOISE_CHARS_RE = re.compile(r"[\uFFFC\u200B\uFEFF]+")

# PDF 文件名（相对 docs2 根目录）→ chroma_db1 下子目录名（即「向量库」分区）
DEFAULT_PDF_PARTITIONS: tuple[tuple[str, str], ...] = (
    (
        "AI大模型原理和应用面试题速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "AI大模型原理和应用面试题",
    ),
    (
        "Java 热门面试题 200 道速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "Java 热门面试题",
    ),
    (
        "Vue 基础面试题速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "前端Vue 基础面试题速",
    ),
)


def _load_md_build_helpers():
    path = Path(__file__).resolve().parent / "build_md_knowledge.py"
    spec = importlib.util.spec_from_file_location("build_md_knowledge_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    text = _MD_IMAGE_RE.sub("", text)
    text = _HTML_IMG_RE.sub("", text)
    text = _NOISE_CHARS_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_one_pdf(
    pdf_path: Path,
    pdf_root: Path,
    chroma_persist: Path,
    *,
    library_key: str,
    collection: str,
    bm,
    emb,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    """单个 PDF → 一个 persist 目录（一套向量库）。"""
    rel = pdf_path.relative_to(pdf_root).as_posix()
    sp_prefix = f"{library_key}/{rel}"
    top = rel.split("/")[0] if "/" in rel else ""

    raw_docs = []
    loader = PyPDFLoader(str(pdf_path))
    for doc in loader.load():
        cleaned = _clean_pdf_text(doc.page_content or "")
        if not cleaned:
            continue
        doc.page_content = cleaned
        doc.metadata["source_path"] = sp_prefix
        doc.metadata["knowledge_base"] = library_key
        doc.metadata["lang"] = "zh"
        doc.metadata["top_section"] = top
        doc.metadata.setdefault("source", str(pdf_path))
        raw_docs.append(doc)

    if not raw_docs:
        raise RuntimeError(f"无可用文本页（空/纯图/加密）：{pdf_path.name}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(raw_docs)
    chunks = [c for c in chunks if (c.page_content or "").strip()]
    if not chunks:
        raise RuntimeError(f"切分后无有效块：{pdf_path.name}")

    print(f"  [{library_key}] 切分 {len(chunks)} 块")

    ids = bm._chunk_ids(chunks)
    chroma_persist.mkdir(parents=True, exist_ok=True)
    db = Chroma.from_documents(
        documents=chunks,
        embedding=emb,
        ids=ids,
        collection_name=collection,
        persist_directory=str(chroma_persist),
    )
    persist_fn = getattr(db, "persist", None)
    if callable(persist_fn):
        persist_fn()
    print(f"  [{library_key}] 已写入 {chroma_persist}")


def build_partitioned_pdfs(
    pdf_root: Path,
    chroma_base: Path,
    partitions: tuple[tuple[str, str], ...],
    *,
    collection: str,
    model_arg: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    hf_cache: str | None = None,
    local_only: bool = False,
) -> None:
    """按分区表逐个 PDF 入库；embedding 只加载一次。"""
    bm = _load_md_build_helpers()
    model_ref = bm._resolve_embedding_model(model_arg)
    print(f"[模型] embedding 加载一次: {model_ref}")
    emb = bm._embeddings(model_ref, hf_cache=hf_cache, local_only=local_only)

    chroma_base.mkdir(parents=True, exist_ok=True)
    for pdf_name, subdir in partitions:
        pdf_path = pdf_root / pdf_name
        out_dir = chroma_base / subdir
        if not pdf_path.is_file():
            print(f"[跳过] 未找到文件: {pdf_path}")
            continue
        print(f"\n[分区] {pdf_name} → {out_dir}")
        _build_one_pdf(
            pdf_path,
            pdf_root,
            out_dir,
            library_key=subdir,
            collection=collection,
            bm=bm,
            emb=emb,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    print("\n[全部完成] 各库位于:", chroma_base)


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="docs2 分区 PDF → chroma_db1 子目录（多向量库）")
    p.add_argument(
        "--docs-dir",
        default="Langchain_knowledge/docs2",
        help="PDF 根目录（相对 backend_langchain）",
    )
    p.add_argument(
        "--chroma-dir",
        default="Langchain_knowledge/chroma_db1",
        help="Chroma 根目录（相对 backend_langchain）；其下为各分区子目录",
    )
    p.add_argument(
        "--collection-name",
        default="md_knowledge",
        help="各分区内 collection 名（须与 Langchain_Agent1/tools.py 中 _COLLECTION_NAME 一致）",
    )
    p.add_argument(
        "--embedding-model",
        default="BAAI/bge-small-zh-v1.5",
        help="HuggingFace 模型 id 或本地模型目录",
    )
    p.add_argument("--hf-cache-dir", default=None)
    p.add_argument("--local-only", action="store_true")
    p.add_argument("--chunk-size", type=int, default=1000)
    p.add_argument("--chunk-overlap", type=int, default=150)

    args = p.parse_args()
    base_dir = Path(__file__).resolve().parent.parent

    pdf_root = (base_dir / args.docs_dir).resolve()
    chroma_base = (base_dir / args.chroma_dir).resolve()
    if not pdf_root.is_dir():
        raise FileNotFoundError(f"PDF 目录不存在: {pdf_root}")

    build_partitioned_pdfs(
        pdf_root,
        chroma_base,
        DEFAULT_PDF_PARTITIONS,
        collection=args.collection_name,
        model_arg=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        hf_cache=args.hf_cache_dir,
        local_only=args.local_only,
    )


if __name__ == "__main__":
    main()
