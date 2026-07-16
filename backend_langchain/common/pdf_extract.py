"""PDF 字节 → 纯文本（PyPDFLoader + 与建库相同的 clean_pdf_text）。"""
from __future__ import annotations

import base64
import sys
import tempfile
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader

_SCRIPTS = Path(__file__).resolve().parent.parent / "Scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from file_cleanup import clean_pdf_text  # noqa: E402


def _decode_data_url(data_url: str) -> bytes:
    s = (data_url or "").strip()
    if not s or "," not in s:
        return b""
    try:
        return base64.b64decode(s.split(",", 1)[1], validate=False)
    except Exception:
        return b""


def extract_pdf_text(data: bytes) -> str:
    if not data:
        return ""
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        parts: list[str] = []
        for page in PyPDFLoader(path).load():
            text = clean_pdf_text(page.page_content or "")
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip()
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def extract_pdf_text_from_data_url(data_url: str) -> str:
    return extract_pdf_text(_decode_data_url(data_url))
