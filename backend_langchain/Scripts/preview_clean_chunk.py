"""
清洗 + 切块效果预览：从知识库等目录抽 10 份代表性文件，导出到 common/data/clean_chunk_preview/。

用法（backend_langchain 目录）：
  python Scripts/preview_clean_chunk.py
  python Scripts/preview_clean_chunk.py --max-chunks 8   # 每文件最多导出 N 个 chunk
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from langchain_core.documents import Document

from common.document_pipeline.ingest import chunks_from_path, load_documents_for_path
from config.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, knowledge_root

OUT_DIR = _ROOT / "common" / "data" / "clean_chunk_preview"
RAW_HEAD_CHARS = 2500


@dataclass(frozen=True)
class SampleSpec:
    slug: str
    rel_path: str
    fmt: str
    domain: str
    note: str


# 10 份样本：md×5、pdf×3、txt×1、json×1（不同来源/版式）
SAMPLES: tuple[SampleSpec, ...] = (
    SampleSpec(
        "01_md_ai_model",
        "docs1/ai_programming/01 AI 模型选择指南.md",
        "markdown",
        "ai_programming",
        "教程 Markdown，含图片链接与列表",
    ),
    SampleSpec(
        "02_md_openclaw",
        "docs1/openclaw/00 OpenClaw 保姆级教程导读.md",
        "markdown",
        "openclaw",
        "OpenClaw 导读，多级标题",
    ),
    SampleSpec(
        "03_md_vibe_long",
        "docs1/vibe_coding/70 Vibe Coding 概念大全.md",
        "markdown",
        "vibe_coding",
        "长文 Markdown",
    ),
    SampleSpec(
        "04_md_mcp_code",
        "docs1/learn_programing/MCP 服务开发.md",
        "markdown",
        "learn_programing",
        "含代码块与术语",
    ),
    SampleSpec(
        "05_md_readme_short",
        "docs1/vibe_coding/README.md",
        "markdown",
        "vibe_coding",
        "短 README",
    ),
    SampleSpec(
        "06_pdf_interview_java",
        "docs2/interview_java/Java 热门面试题 200 道速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "pdf",
        "interview_java",
        "面试 PDF",
    ),
    SampleSpec(
        "07_pdf_interview_llm",
        "docs2/interview_llm/AI大模型原理和应用面试题速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "pdf",
        "interview_llm",
        "大模型面试 PDF",
    ),
    SampleSpec(
        "08_pdf_interview_vue",
        "docs2/interview_vue/Vue 基础面试题速记通关版 _ 面试刷题 mianshiya.com.pdf",
        "pdf",
        "interview_vue",
        "Vue 面试 PDF",
    ),
    SampleSpec(
        "09_txt_requirements",
        "../requirements.txt",
        "text",
        "project",
        "纯文本依赖清单（无 Markdown 结构）",
    ),
    SampleSpec(
        "10_json_mcp_config",
        "../MCP/mcp_servers.example.json",
        "json",
        "project",
        "JSON 配置（按纯文本清洗切块）",
    ),
)


def _read_raw(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "(PDF 二进制，见 raw_head 为抽取说明)"
    return path.read_text(encoding="utf-8", errors="replace")


def _corpus_for_fmt(fmt: str) -> str:
    if fmt == "pdf":
        return "interview"
    if fmt == "markdown":
        return "agent"
    return "preview"


def _documents_for_sample(spec: SampleSpec, abs_path: Path) -> list[Document]:
    root = knowledge_root()
    return load_documents_for_path(
        abs_path,
        root,
        corpus=_corpus_for_fmt(spec.fmt),
        domain=spec.domain,
        fmt=spec.fmt,
    )


def _chunk_documents(docs: list[Document], *, abs_path: Path, fmt: str) -> list[Document]:
    if not docs:
        return []
    root = knowledge_root()
    domain = str(docs[0].metadata.get("domain", "preview")) if docs else "preview"
    return chunks_from_path(
        abs_path,
        root,
        corpus=_corpus_for_fmt(fmt),
        domain=domain,
        fmt=fmt,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _export_sample(
    spec: SampleSpec,
    *,
    max_chunks: int,
    chunk_size: int,
    chunk_overlap: int,
) -> dict:
    abs_path = (knowledge_root() / spec.rel_path).resolve()
    if spec.rel_path.startswith("../"):
        abs_path = (_ROOT / spec.rel_path.removeprefix("../")).resolve()

    if not abs_path.is_file():
        raise FileNotFoundError(abs_path)

    raw_full = _read_raw(abs_path)
    raw_head = raw_full[:RAW_HEAD_CHARS] if not raw_full.startswith("(PDF") else (
        f"PDF 文件: {abs_path.name}\n大小: {abs_path.stat().st_size} bytes\n"
        "正文见 cleaned.txt（pdfplumber 抽取后清洗）"
    )

    docs = _documents_for_sample(spec, abs_path)
    cleaned_full = "\n\n---\n\n".join(
        (d.page_content or "").strip() for d in docs if (d.page_content or "").strip()
    )
    chunks = _chunk_documents(docs, abs_path=abs_path, fmt=spec.fmt)
    total_chunks = len(chunks)
    if max_chunks > 0:
        chunks = chunks[:max_chunks]

    out_base = OUT_DIR / spec.slug
    _write_text(
        out_base / "meta.txt",
        "\n".join(
            [
                f"slug: {spec.slug}",
                f"format: {spec.fmt}",
                f"domain: {spec.domain}",
                f"note: {spec.note}",
                f"source: {abs_path}",
                f"chunk_size: {chunk_size}",
                f"chunk_overlap: {chunk_overlap}",
                f"raw_chars: {len(raw_full) if not raw_full.startswith('(PDF') else 'n/a'}",
                f"cleaned_chars: {len(cleaned_full)}",
                f"chunk_count_total: {total_chunks}",
                f"chunk_count_exported: {len(chunks)}",
            ]
        ),
    )
    _write_text(out_base / "raw_head.txt", raw_head)
    _write_text(out_base / "cleaned.txt", cleaned_full or "(清洗后为空)")

    for i, ch in enumerate(chunks, start=1):
        meta = ch.metadata or {}
        header = (
            f"--- chunk {i} ---\n"
            f"source_path: {meta.get('source_path', '')}\n"
            f"corpus: {meta.get('corpus', '')} | domain: {meta.get('domain', '')}\n"
            f"chars: {len(ch.page_content or '')}\n"
            f"---\n"
        )
        _write_text(out_base / "chunks" / f"chunk_{i:03d}.txt", header + (ch.page_content or ""))

    return {
        "slug": spec.slug,
        "format": spec.fmt,
        "domain": spec.domain,
        "note": spec.note,
        "source": str(abs_path),
        "raw_chars": len(raw_full) if not raw_full.startswith("(PDF") else None,
        "cleaned_chars": len(cleaned_full),
        "chunk_count": total_chunks,
        "exported_chunks": len(chunks),
        "empty_after_clean": not bool(cleaned_full.strip()),
    }


def _write_index(manifest: list[dict]) -> None:
    lines = [
        "# 清洗 + 切块效果预览",
        "",
        f"输出目录: `{OUT_DIR.relative_to(_ROOT).as_posix()}`",
        "",
        "| # | slug | 格式 | 清洗后字数 | chunk 数 | 说明 |",
        "|---|------|------|------------|----------|------|",
    ]
    for i, row in enumerate(manifest, start=1):
        lines.append(
            f"| {i} | `{row['slug']}` | {row['format']} | "
            f"{row['cleaned_chars']} | {row['chunk_count']} | {row['note']} |"
        )
    lines.extend(
        [
            "",
            "## 每个样本目录",
            "",
            "- `meta.txt` — 元信息",
            "- `raw_head.txt` — 原文前若干字符",
            "- `cleaned.txt` — 清洗后全文",
            "- `chunks/chunk_XXX.txt` — 切块结果（含字符数）",
            "",
            "重新生成: `python Scripts/preview_clean_chunk.py`",
        ]
    )
    _write_text(OUT_DIR / "index.md", "\n".join(lines))
    _write_text(OUT_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description="导出清洗切块预览到 common/data/clean_chunk_preview")
    p.add_argument(
        "--max-chunks",
        type=int,
        default=12,
        help="每个文件最多导出几个 chunk（0=全部）",
    )
    args = p.parse_args()
    max_chunks = args.max_chunks if args.max_chunks > 0 else 10_000

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    manifest: list[dict] = []
    print(f"==> 输出: {OUT_DIR}")
    for spec in SAMPLES:
        print(f"  处理: {spec.slug} ({spec.fmt})")
        row = _export_sample(
            spec,
            max_chunks=max_chunks,
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        )
        manifest.append(row)

    _write_index(manifest)
    print(f"==> 完成 {len(manifest)} 个样本，见 {OUT_DIR / 'index.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
