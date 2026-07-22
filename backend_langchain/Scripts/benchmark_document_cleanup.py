"""
文档清洗 + 切块压测（10 份代表性样本）。

用法（backend_langchain 目录）：
  python Scripts/benchmark_document_cleanup.py
  python Scripts/benchmark_document_cleanup.py --json   # 额外写出 JSON
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

warnings.filterwarnings("ignore", message=".*FontBBox.*")
logging.getLogger("pdfminer").setLevel(logging.ERROR)

from common.document_pipeline.ingest import chunks_from_path, load_documents_for_path
from config.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, knowledge_root
from preview_clean_chunk import SAMPLES, SampleSpec

_H2 = re.compile(r"^##\s")
_SPACED_LATIN = re.compile(r"\b(?:[A-Za-z]\s+){1,}[A-Za-z]\b")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


@dataclass
class SampleMetrics:
    slug: str
    format: str
    domain: str
    raw_chars: int | None
    raw_bytes: int
    cleaned_chars: int
    shrink_pct: float | None
    chunk_count: int
    chunk_min: int
    chunk_max: int
    chunk_avg: float
    chunk_p50: float
    chunks_lt_80: int
    chunks_lt_200_no_header: int
    chunks_over_size: int
    elapsed_sec: float
    notes: list[str]


def _resolve_path(spec: SampleSpec) -> Path:
    if spec.rel_path.startswith("../"):
        return (_ROOT / spec.rel_path.removeprefix("../")).resolve()
    return (knowledge_root() / spec.rel_path).resolve()


def _corpus_for_fmt(fmt: str) -> str:
    if fmt == "pdf":
        return "interview"
    if fmt == "markdown":
        return "agent"
    return "preview"


def _raw_chars(path: Path, fmt: str) -> int | None:
    if fmt == "pdf":
        return None
    return len(path.read_text(encoding="utf-8", errors="replace"))


def _quality_notes(spec: SampleSpec, raw: str | None, cleaned: str, chunks: list) -> list[str]:
    notes: list[str] = []
    texts = [c.page_content or "" for c in chunks]

    if spec.fmt == "markdown" and raw:
        img_raw = len(_MD_IMAGE.findall(raw))
        img_clean = len(_MD_IMAGE.findall(cleaned))
        if img_raw and img_clean == 0:
            notes.append(f"图片链接已去除 ({img_raw}→0)")
        elif img_raw:
            notes.append(f"图片链接残留 {img_clean}/{img_raw}")

    if spec.fmt == "pdf":
        spaced = len(_SPACED_LATIN.findall(cleaned))
        notes.append(f"拉丁粘连残留行 {spaced}")

    if spec.slug == "04_md_mcp_code":
        ok = any("<groupId>" in t for t in texts)
        notes.append("代码块 <groupId> 保留" if ok else "代码块 <groupId> 丢失")

    if spec.slug == "09_txt_requirements":
        ok = any("<1.0" in t for t in texts)
        notes.append("依赖版本 <1.0 保留" if ok else "依赖版本 <1.0 丢失")

    if spec.fmt == "pdf":
        from common.document_pipeline.cleanup import is_pdf_question_line

        q_lines = sum(1 for ln in cleaned.splitlines() if is_pdf_question_line(ln))
        q_chunks = sum(1 for t in texts if t.strip() and is_pdf_question_line(t.splitlines()[0]))
        notes.append(f"问句行 {q_lines}，问句起始 chunk {q_chunks}/{len(texts)}")

    return notes


def benchmark_sample(spec: SampleSpec) -> SampleMetrics:
    path = _resolve_path(spec)
    if not path.is_file():
        raise FileNotFoundError(path)

    corpus = _corpus_for_fmt(spec.fmt)
    root = knowledge_root()

    t0 = time.perf_counter()
    docs = load_documents_for_path(path, root, corpus=corpus, domain=spec.domain, fmt=spec.fmt)
    cleaned = "\n\n".join((d.page_content or "").strip() for d in docs if (d.page_content or "").strip())
    chunks = chunks_from_path(
        path, root, corpus=corpus, domain=spec.domain, fmt=spec.fmt,
        chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    elapsed = time.perf_counter() - t0

    raw_c = _raw_chars(path, spec.fmt)
    sizes = [len(c.page_content or "") for c in chunks]
    shrink = None
    if raw_c and raw_c > 0:
        shrink = round((1 - len(cleaned) / raw_c) * 100, 1)

    lt80 = sum(1 for s in sizes if s < 80)
    lt200_nh = 0
    for c in chunks:
        t = (c.page_content or "").strip()
        if not t:
            continue
        first = (t.splitlines() or [""])[0]
        if len(t) < 200 and not _H2.match(first) and not first.startswith("###"):
            lt200_nh += 1

    notes = _quality_notes(spec, None if spec.fmt == "pdf" else path.read_text(encoding="utf-8", errors="replace"), cleaned, chunks)

    return SampleMetrics(
        slug=spec.slug,
        format=spec.fmt,
        domain=spec.domain,
        raw_chars=raw_c,
        raw_bytes=path.stat().st_size,
        cleaned_chars=len(cleaned),
        shrink_pct=shrink,
        chunk_count=len(chunks),
        chunk_min=min(sizes) if sizes else 0,
        chunk_max=max(sizes) if sizes else 0,
        chunk_avg=round(statistics.mean(sizes), 1) if sizes else 0.0,
        chunk_p50=round(statistics.median(sizes), 1) if sizes else 0.0,
        chunks_lt_80=lt80,
        chunks_lt_200_no_header=lt200_nh,
        chunks_over_size=sum(1 for s in sizes if s > DEFAULT_CHUNK_SIZE),
        elapsed_sec=round(elapsed, 2),
        notes=notes,
    )


def _print_table(rows: list[SampleMetrics]) -> None:
    print(f"\n配置: chunk_size={DEFAULT_CHUNK_SIZE}, overlap={DEFAULT_CHUNK_OVERLAP}\n")
    hdr = (
        f"{'slug':<22} {'fmt':<8} {'raw':>8} {'clean':>8} {'缩%':>6} "
        f"{'chunks':>6} {'avg':>6} {'p50':>6} {'min':>5} {'max':>5} "
        f"{'<80':>4} {'孤儿':>4} {'>size':>5} {'sec':>6}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        raw_s = str(r.raw_chars) if r.raw_chars is not None else "pdf"
        shrink_s = f"{r.shrink_pct:.1f}" if r.shrink_pct is not None else "n/a"
        print(
            f"{r.slug:<22} {r.format:<8} {raw_s:>8} {r.cleaned_chars:>8} {shrink_s:>6} "
            f"{r.chunk_count:>6} {r.chunk_avg:>6.0f} {r.chunk_p50:>6.0f} {r.chunk_min:>5} "
            f"{r.chunk_max:>5} {r.chunks_lt_80:>4} {r.chunks_lt_200_no_header:>4} "
            f"{r.chunks_over_size:>5} {r.elapsed_sec:>6.1f}"
        )

    print("\n质量抽检:")
    for r in rows:
        print(f"  {r.slug}: {'; '.join(r.notes)}")

    by_fmt: dict[str, list[SampleMetrics]] = {}
    for r in rows:
        by_fmt.setdefault(r.format, []).append(r)

    print("\n按格式汇总:")
    for fmt, items in sorted(by_fmt.items()):
        total_chunks = sum(x.chunk_count for x in items)
        total_clean = sum(x.cleaned_chars for x in items)
        total_sec = sum(x.elapsed_sec for x in items)
        orphans = sum(x.chunks_lt_200_no_header for x in items)
        print(
            f"  {fmt}: 样本 {len(items)}, 清洗后 {total_clean:,} 字, "
            f"chunk {total_chunks}, 孤儿块 {orphans}, 耗时 {total_sec:.1f}s"
        )

    print(
        f"\n合计: 清洗后 {sum(r.cleaned_chars for r in rows):,} 字, "
        f"chunk {sum(r.chunk_count for r in rows)}, "
        f"耗时 {sum(r.elapsed_sec for r in rows):.1f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="写出 common/data/cleanup_benchmark.json")
    args = parser.parse_args()

    rows: list[SampleMetrics] = []
    for spec in SAMPLES:
        print(f"压测: {spec.slug} ...", flush=True)
        rows.append(benchmark_sample(spec))

    _print_table(rows)

    if args.json:
        out = _ROOT / "common" / "data" / "cleanup_benchmark.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunk_size": DEFAULT_CHUNK_SIZE,
            "chunk_overlap": DEFAULT_CHUNK_OVERLAP,
            "samples": [asdict(r) for r in rows],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
