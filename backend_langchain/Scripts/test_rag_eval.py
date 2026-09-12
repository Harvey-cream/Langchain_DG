"""
RAG 切分与召回评测（不写 pgvector，默认不调用 Embedding API）。

  # 1) 只看切分效果（零成本）
  python Scripts/test_rag_eval.py preview --domain ai_programming --file "00 AI 编程工具大全.md"

  # 2) 小范围召回测试（仅 embed 选中文件，省 API）
  python Scripts/test_rag_eval.py recall --domain ai_programming --file "00 AI 编程工具大全.md"

  # 3) 整个 domain 召回（chunk 多、耗 API，慎用）
  python Scripts/test_rag_eval.py recall --domain ai_programming --max-chunks 80

  # 4) 自定义问句
  python Scripts/test_rag_eval.py recall --domain ai_programming --file "00 AI 编程工具大全.md" -q "Cursor 和 Bolt 区别"
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv

load_dotenv()

from langchain_core.documents import Document

from app.services.document_pipeline import (
    agent_markdown_chunks,
    clean_markdown_text,
    interview_pdf_chunks,
    load_markdown_documents,
    split_documents,
)
from config.config import (
    CORPUS_AGENT,
    CORPUS_INTERVIEW,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    RECALL_K,
    knowledge_root,
    list_domains,
)
# query → 期望 top 结果里应出现的关键词（用于粗算 recall@k）
AGENT_RECALL_CASES: dict[str, list[dict[str, object]]] = {
    "ai_programming": [
        {"query": "零代码平台有哪些代表工具", "keywords": ["零代码", "Bolt", "Lovable"]},
        {"query": "Cursor 属于哪类 AI 编程工具", "keywords": ["Cursor", "代码编辑器"]},
        {"query": "Claude Code 是什么类型的工具", "keywords": ["命令行", "Claude Code"]},
        {"query": "为什么要了解 AI 编程工具", "keywords": ["效率", "工具"]},
    ],
    "openclaw": [
        {"query": "OpenClaw 是什么", "keywords": ["OpenClaw"]},
    ],
    "interview_llm": [
        {"query": "Transformer 自注意力机制", "keywords": ["注意力", "Transformer"]},
    ],
    "interview_java": [
        {"query": "Java HashMap 底层原理", "keywords": ["HashMap"]},
    ],
}

_PREVIEW_CHARS = 280


def _console(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


@dataclass
class ChunkStat:
    source_path: str
    index: int
    chars: int
    lines: int
    preview: str


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return -1.0
    return dot / (na * nb)


def _resolve_md_paths(domain: str, file_glob: str | None) -> list[Path]:
    domain_dir = knowledge_root() / "docs1" / domain
    if not domain_dir.is_dir():
        raise SystemExit(f"目录不存在: {domain_dir}")
    if file_glob:
        paths = sorted(domain_dir.rglob(file_glob))
        if not paths:
            raise SystemExit(f"未找到文件: {domain_dir / file_glob}")
        return paths
    return sorted(domain_dir.rglob("*.md"))


def _collect_agent_chunks(
    domain: str,
    *,
    file_glob: str | None,
    chunk_size: int,
    chunk_overlap: int,
    max_chunks: int | None,
) -> list[Document]:
    root = knowledge_root()
    domain_dir = root / "docs1" / domain
    paths = _resolve_md_paths(domain, file_glob)
    docs = load_markdown_documents(
        paths, root, corpus=CORPUS_AGENT, domain=domain, strip_images=True
    )
    chunks = split_documents(
        docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        markdown_aware=True,
    )
    if max_chunks is not None and len(chunks) > max_chunks:
        print(f"[截断] chunks {len(chunks)} → {max_chunks}（可用 --max-chunks 调整）")
        chunks = chunks[:max_chunks]
    return chunks


def _chunk_stats(chunks: list[Document]) -> list[ChunkStat]:
    out: list[ChunkStat] = []
    for i, ch in enumerate(chunks):
        text = (ch.page_content or "").strip()
        sp = (ch.metadata or {}).get("source_path", "")
        preview = text[:_PREVIEW_CHARS].replace("\n", " | ")
        if len(text) > _PREVIEW_CHARS:
            preview += "…"
        out.append(
            ChunkStat(
                source_path=str(sp),
                index=i,
                chars=len(text),
                lines=text.count("\n") + 1 if text else 0,
                preview=preview,
            )
        )
    return out


def _print_chunk_summary(chunks: list[Document]) -> None:
    if not chunks:
        print("（无 chunk）")
        return
    lens = [len((c.page_content or "").strip()) for c in chunks]
    print(f"共 {len(chunks)} 块 | 字数 min={min(lens)} max={max(lens)} avg={sum(lens)//len(lens)}")
    by_source: dict[str, int] = {}
    for c in chunks:
        sp = (c.metadata or {}).get("source_path", "?")
        by_source[sp] = by_source.get(sp, 0) + 1
    print("按文件:", ", ".join(f"{Path(k).name}×{v}" for k, v in sorted(by_source.items())))


def cmd_preview(args: argparse.Namespace) -> None:
    chunks = _collect_agent_chunks(
        args.domain,
        file_glob=args.file,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_chunks=args.max_chunks,
    )
    print(f"\n=== 切分预览 domain={args.domain} chunk={args.chunk_size}/{args.chunk_overlap} ===")
    _print_chunk_summary(chunks)

    if args.file and len(_resolve_md_paths(args.domain, args.file)) == 1:
        raw = _resolve_md_paths(args.domain, args.file)[0].read_text(encoding="utf-8")
        clean = clean_markdown_text(raw)
        print(f"\n清洗: {len(raw)} 字 / {len(raw.splitlines())} 行 → {len(clean)} 字 / {len(clean.splitlines())} 行 "
              f"(减少 {len(raw)-len(clean)} 字)")

    show = args.show if args.show > 0 else min(12, len(chunks))
    print(f"\n--- 前 {show} 块预览 ---")
    for st in _chunk_stats(chunks)[:show]:
        print(_console(f"\n[{st.index}] {st.source_path} ({st.chars}字/{st.lines}行)"))
        print(_console(st.preview))

    if args.keyword:
        hits = [
            i
            for i, c in enumerate(chunks)
            if args.keyword in (c.page_content or "")
        ]
        print(f"\n--- 关键词「{args.keyword}」命中 {len(hits)} 块: {hits[:20]} ---")


def _embed_batches(emb, texts: list[str], batch: int) -> list[list[float]]:
    vecs: list[list[float]] = []
    for i in range(0, len(texts), batch):
        vecs.extend(emb.embed_documents(texts[i : i + batch]))
    return vecs


def _keyword_hit(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def cmd_recall(args: argparse.Namespace) -> None:
    from infrastructure.rag.embedding import get_rag_embedding_model
    from config.config import dashscope_embedding_batch_size, dashscope_model_name

    cases = list(AGENT_RECALL_CASES.get(args.domain, []))
    if args.query:
        cases.append({"query": args.query, "keywords": []})

    if not cases:
        raise SystemExit(f"domain={args.domain} 无内置问句，请用 -q 指定")

    chunks = _collect_agent_chunks(
        args.domain,
        file_glob=args.file,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        max_chunks=args.max_chunks,
    )
    if not chunks:
        raise SystemExit("无 chunk，无法评测")

    texts = [(c.page_content or "").strip() for c in chunks]
    print(f"\n=== 召回评测 domain={args.domain} | {dashscope_model_name()} | chunks={len(texts)} ===")
    print(f"预计 embed 调用约 {1 + math.ceil(len(texts) / dashscope_embedding_batch_size())} 次 "
          f"(query×{len(cases)} + documents)")

    if not args.yes:
        ans = input("继续调用 DashScope 嵌入? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消")
            return

    emb = get_rag_embedding_model()
    batch = dashscope_embedding_batch_size()
    doc_vecs = _embed_batches(emb, texts, batch)

    top_k = args.top_k
    hits_at_1 = hits_at_3 = hits_at_k = 0
    total_kw = 0

    for case in cases:
        q = str(case["query"])
        keywords = [str(k) for k in case.get("keywords", [])]
        qvec = emb.embed_query(q)
        scored = sorted(
            (( _cosine(qvec, dv), i) for i, dv in enumerate(doc_vecs)),
            key=lambda x: x[0],
            reverse=True,
        )
        top = scored[:top_k]

        print(f"\n问: {q}")
        if keywords:
            print(f"期望关键词: {keywords}")
        for rank, (score, idx) in enumerate(top[:5], start=1):
            sp = (chunks[idx].metadata or {}).get("source_path", "")
            body = texts[idx][:200].replace("\n", " ")
            print(_console(f"  #{rank} score={score:.4f} [{Path(sp).name}] {body}…"))

        if keywords:
            total_kw += 1
            in_top = [idx for _, idx in top]
            if any(_keyword_hit(texts[i], keywords) for i in in_top[:1]):
                hits_at_1 += 1
            if any(_keyword_hit(texts[i], keywords) for i in in_top[:3]):
                hits_at_3 += 1
            if any(_keyword_hit(texts[i], keywords) for i in in_top):
                hits_at_k += 1
            matched = [i for i in in_top if _keyword_hit(texts[i], keywords)]
            print(f"  关键词命中@1/3/{top_k}: "
                  f"{'Y' if matched and matched[0] in in_top[:1] else 'N'}/"
                  f"{'Y' if any(i in in_top[:3] for i in matched) else 'N'}/"
                  f"{'Y' if matched else 'N'}")

    if total_kw:
        print(f"\n=== 汇总（有关键词标注的 {total_kw} 题）===")
        print(f"  keyword recall@1: {hits_at_1}/{total_kw} ({100*hits_at_1/total_kw:.0f}%)")
        print(f"  keyword recall@3: {hits_at_3}/{total_kw} ({100*hits_at_3/total_kw:.0f}%)")
        print(f"  keyword recall@{top_k}: {hits_at_k}/{total_kw} ({100*hits_at_k/total_kw:.0f}%)")


def main() -> None:
    domains = sorted(list_domains(CORPUS_AGENT))
    p = argparse.ArgumentParser(description="RAG 切分预览与召回评测（不写库）")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--domain", default="ai_programming", choices=sorted(domains) if domains else None)
    common.add_argument("--file", default=None, help="仅测单个 md，如 '00 AI 编程工具大全.md'")
    common.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    common.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    common.add_argument("--max-chunks", type=int, default=None, help="限制 embed 块数，省 API")

    prev = sub.add_parser("preview", parents=[common], help="只看切分/清洗，不 embed")
    prev.add_argument("--show", type=int, default=12, help="打印前 N 块")
    prev.add_argument("--keyword", default=None, help="统计含该词的块序号")

    rec = sub.add_parser("recall", parents=[common], help="小范围 embed + 召回打分")
    rec.add_argument("-q", "--query", action="append", default=[], help="自定义问句，可重复")
    rec.add_argument("--top-k", type=int, default=RECALL_K)
    rec.add_argument("-y", "--yes", action="store_true", help="跳过确认直接 embed")

    args = p.parse_args()
    if args.cmd == "preview":
        cmd_preview(args)
    else:
        cmd_recall(args)


if __name__ == "__main__":
    main()
