"""PDF 文本抽取：pdfplumber（文件路径 / 字节 / data URL）。"""
from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from app.services.document_pipeline.cleanup import clean_pdf_text


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """返回 (页码从 1 起, 该页原始文本)。"""
    import pdfplumber

    pages: list[tuple[int, str]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i, text))
    return pages


def _decode_data_url(data_url: str) -> bytes:
    s = (data_url or "").strip()
    if not s or "," not in s:
        return b""
    try:
        return base64.b64decode(s.split(",", 1)[1], validate=False)
    except Exception:
        return b""


def extract_pdf_text(data: bytes) -> str:
    """PDF 字节 → 清洗后纯文本（与建库流水线一致）。"""
    if not data:
        return ""
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        parts: list[str] = []
        for _page_num, raw in extract_pdf_pages(Path(path)):
            text = clean_pdf_text(raw)
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip()
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def extract_pdf_text_from_data_url(data_url: str) -> str:
    return extract_pdf_text(_decode_data_url(data_url))
