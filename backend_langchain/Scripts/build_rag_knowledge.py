"""
构建 RAG 向量库：扫描 docs1/docs2 子目录，向量化写入 Chroma。
约定：docs1/<domain>/**/*.md → agent；docs2/<domain>/**/*.pdf → interview。

  python Scripts/build_rag_knowledge.py
  python Scripts/build_rag_knowledge.py --append
"""
from __future__ import annotations

import argparse
import shutil
import stat
import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from common.document_pipeline import agent_markdown_chunks, existing_source_paths, interview_pdf_chunks
from common.embedding import get_rag_embedding_model
from config.config import (
    COLLECTION,
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    DOCS_AGENT,
    DOCS_INTERVIEW,
    chroma_path,
    dashscope_dimensions,
    dashscope_model_name,
    knowledge_root,
    list_domains,
)


def _domain_dirs(corpus: str) -> list[Path]:
    root = knowledge_root()
    docs = root / (DOCS_AGENT if corpus == CORPUS_AGENT else DOCS_INTERVIEW)
    return sorted(docs / n for n in sorted(list_domains(corpus)))


def _on_rm_error(func, path, _exc_info) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _clear_chroma_dir(chroma_dir: Path) -> None:
    if not chroma_dir.exists():
        return
    last_err: PermissionError | None = None
    for attempt in range(5):
        try:
            shutil.rmtree(chroma_dir, onerror=_on_rm_error)
            print("[重建] 已清空库目录")
            return
        except PermissionError as e:
            last_err = e
            if attempt < 4:
                print(f"[等待] 目录占用中，重试 ({attempt + 1}/5)…")
                time.sleep(1.5)
    raise SystemExit(
        "无法清空向量库：Chroma 数据文件正被其他进程占用（通常是正在运行的 uvicorn）。\n"
        f"  路径: {chroma_dir}\n"
        "  请先 Ctrl+C 停掉 API 服务，再执行本脚本；或改用 --append 增量写入。"
    ) from last_err


def vectorize(
    chroma_dir: Path,
    chunks: list[Document],
    emb: Embeddings,
    *,
    append: bool,
) -> None:
    if not chunks:
        return
    chroma_dir.mkdir(parents=True, exist_ok=True)
    if append:
        Chroma(
            persist_directory=str(chroma_dir),
            embedding_function=emb,
            collection_name=COLLECTION,
        ).add_documents(chunks)
    else:
        Chroma.from_documents(
            documents=chunks,
            embedding=emb,
            collection_name=COLLECTION,
            persist_directory=str(chroma_dir),
        )


def build_rag_knowledge(
    chroma_dir: Path,
    *,
    agent_domains: list[str] | None,
    do_interview: bool,
    append: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    strip_images: bool = True,
) -> None:
    emb = get_rag_embedding_model()
    root = knowledge_root()
    print(f"DashScope {dashscope_model_name()} ({dashscope_dimensions()} 维) → {chroma_dir}")

    if not append and chroma_dir.exists():
        _clear_chroma_dir(chroma_dir)

    agent_dirs = _domain_dirs(CORPUS_AGENT)
    if agent_domains is not None:
        wanted = set(agent_domains)
        agent_dirs = [d for d in agent_dirs if d.name in wanted]
        if missing := wanted - {d.name for d in agent_dirs}:
            raise SystemExit(f"未找到 agent domain 目录: {sorted(missing)}")

    skip = existing_source_paths(chroma_dir, collection=COLLECTION) if append else set()
    wrote = False

    for domain_dir in agent_dirs:
        chunks = agent_markdown_chunks(
            domain_dir,
            root,
            corpus=CORPUS_AGENT,
            domain=domain_dir.name,
            skip_sources=skip,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strip_images=strip_images,
        )
        if not chunks:
            print(f"[跳过] agent/{domain_dir.name} 无新 md")
            continue
        print(f"\n--- agent/{domain_dir.name} --- 向量化 {len(chunks)} 块")
        vectorize(chroma_dir, chunks, emb, append=wrote)
        wrote = True
        if append:
            skip = existing_source_paths(chroma_dir, collection=COLLECTION)

    if do_interview:
        for domain_dir in _domain_dirs(CORPUS_INTERVIEW):
            for pdf in sorted(domain_dir.rglob("*.pdf")):
                sp = pdf.relative_to(root).as_posix()
                if append and sp in skip:
                    continue
                chunks = interview_pdf_chunks(
                    pdf,
                    root,
                    corpus=CORPUS_INTERVIEW,
                    domain=domain_dir.name,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                print(f"\n--- interview/{domain_dir.name} --- {pdf.name} → {len(chunks)} 块")
                vectorize(chroma_dir, chunks, emb, append=wrote)
                wrote = True

    print("\n[完成] 无需处理。" if not wrote else f"\n[完成] {chroma_dir} | collection={COLLECTION}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="扫描 docs1/docs2 并向量化写入 knowledge 库")
    p.add_argument("--chroma-dir", default=None)
    p.add_argument("--only", nargs="+", metavar="DOMAIN", help="仅处理指定 docs1 子目录名")
    p.add_argument("--interview-only", action="store_true")
    p.add_argument("--skip-interview", action="store_true")
    p.add_argument("--append", action="store_true")
    p.add_argument("--chunk-size", type=int, default=1000)
    p.add_argument("--chunk-overlap", type=int, default=150)
    p.add_argument("--no-strip-images", action="store_true")
    args = p.parse_args()

    if args.interview_only and args.only:
        p.error("--interview-only 与 --only 不能同时使用")
    if args.interview_only and args.skip_interview:
        p.error("--interview-only 与 --skip-interview 冲突")

    if args.interview_only:
        agent_domains: list[str] | None = []
        do_interview = True
    elif args.only:
        agent_domains = list(args.only)
        do_interview = False
    else:
        agent_domains = None
        do_interview = not args.skip_interview

    build_rag_knowledge(
        (_ROOT / args.chroma_dir).resolve() if args.chroma_dir else chroma_path(),
        agent_domains=agent_domains,
        do_interview=do_interview,
        append=args.append,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        strip_images=not args.no_strip_images,
    )


if __name__ == "__main__":
    main()
