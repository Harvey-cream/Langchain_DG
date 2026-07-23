"""
构建 RAG 向量库：扫描 docs1/docs2 子目录，向量化写入 pgvector（表 rag_embeddings）。
约定：docs1/<domain>/**/*.md → corpus=agent；docs2/<domain>/**/*.pdf → corpus=interview。

  python Scripts/build_rag_knowledge.py
  python Scripts/build_rag_knowledge.py --append
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv

load_dotenv()

from common.document_pipeline import agent_markdown_chunks, interview_pdf_chunks
from common.pgvector_store import PgVectorStore
from common.rag import get_store
from config.config import (
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    DOCS_AGENT,
    DOCS_INTERVIEW,
    dashscope_dimensions,
    dashscope_model_name,
    knowledge_root,
    list_domains,
)


def _domain_dirs(corpus: str) -> list[Path]:
    root = knowledge_root()
    docs = root / (DOCS_AGENT if corpus == CORPUS_AGENT else DOCS_INTERVIEW)
    return sorted(docs / n for n in sorted(list_domains(corpus)))


def build_rag_knowledge(
    store: PgVectorStore,
    *,
    agent_domains: list[str] | None,
    do_interview: bool,
    append: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    strip_images: bool = True,
) -> None:
    root = knowledge_root()
    print(f"DashScope {dashscope_model_name()} ({dashscope_dimensions()} 维) → pgvector rag_embeddings")
    store.setup()

    agent_dirs = _domain_dirs(CORPUS_AGENT)
    if agent_domains is not None:
        wanted = set(agent_domains)
        agent_dirs = [d for d in agent_dirs if d.name in wanted]
        if missing := wanted - {d.name for d in agent_dirs}:
            raise SystemExit(f"未找到 agent domain 目录: {sorted(missing)}")

    # 全量重建：清空将要处理的 corpus；增量：按已有 source_path 跳过
    if not append:
        if agent_dirs:
            removed = store.clear_corpus(CORPUS_AGENT)
            print(f"[重建] 已清空 corpus=agent（{removed} 行）")
        if do_interview:
            removed = store.clear_corpus(CORPUS_INTERVIEW)
            print(f"[重建] 已清空 corpus=interview（{removed} 行）")

    agent_skip = store.list_source_paths(corpus=CORPUS_AGENT) if append else set()
    wrote = False

    for domain_dir in agent_dirs:
        chunks = agent_markdown_chunks(
            domain_dir,
            root,
            corpus=CORPUS_AGENT,
            domain=domain_dir.name,
            skip_sources=agent_skip,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strip_images=strip_images,
        )
        if not chunks:
            print(f"[跳过] agent/{domain_dir.name} 无新 md")
            continue
        print(f"\n--- agent/{domain_dir.name} --- 向量化 {len(chunks)} 块")
        store.add(chunks)
        wrote = True
        if append:
            agent_skip = store.list_source_paths(corpus=CORPUS_AGENT)

    if do_interview:
        interview_skip = store.list_source_paths(corpus=CORPUS_INTERVIEW) if append else set()
        for domain_dir in _domain_dirs(CORPUS_INTERVIEW):
            for pdf in sorted(domain_dir.rglob("*.pdf")):
                sp = pdf.relative_to(root).as_posix()
                if append and sp in interview_skip:
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
                store.add(chunks)
                wrote = True

    total = store.count()
    print("\n[完成] 无需处理。" if not wrote else f"\n[完成] rag_embeddings 共 {total} 行")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="扫描 docs1/docs2 并向量化写入 pgvector rag_embeddings")
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
        get_store(),
        agent_domains=agent_domains,
        do_interview=do_interview,
        append=args.append,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        strip_images=not args.no_strip_images,
    )


if __name__ == "__main__":
    main()
