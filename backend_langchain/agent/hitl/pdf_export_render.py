"""把模型生成的 Markdown/文本写入 PDF（fpdf2 + 中文字体），不做复杂排版引擎。"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

_MAX_MARKDOWN_CHARS = 200_000
_FONT_FAMILY = "PdfCJK"
_font_file: Path | None = None


def _project_font_dir() -> Path:
    from app.settings import MEDIA_ROOT

    d = Path(MEDIA_ROOT) / "pdf_fonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pick_source_font() -> Path | None:
    env_path = (os.environ.get("PDF_EXPORT_FONT") or "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
    if os.name == "nt":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for name in ("simhei.ttf", "simkai.ttf"):
            p = windir / name
            if p.is_file():
                return p
        # fpdf2 对 TTC 支持不稳定，仅作最后回退
        for name in ("msyh.ttc", "simsun.ttc"):
            p = windir / name
            if p.is_file():
                return p
    else:
        for cand in (
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ):
            p = Path(cand)
            if p.is_file():
                return p
    return None


def _ensure_font_file() -> Path:
    """系统字体拷到 MEDIA，避免直接读 Windows\\Fonts 出权限问题。"""
    global _font_file
    if _font_file is not None and _font_file.is_file():
        return _font_file

    src = _pick_source_font()
    if src is None:
        raise RuntimeError(
            "未找到可用中文字体。请设置 PDF_EXPORT_FONT 为 .ttf 完整路径 "
            r"（例如 C:\Windows\Fonts\simhei.ttf）"
        )

    dest = _project_font_dir() / src.name
    try:
        if (not dest.is_file()) or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        _font_file = dest
    except OSError:
        _font_file = src
    logger.info("PDF 导出字体: %s", _font_file)
    return _font_file


def _slug_filename(title: str) -> str:
    s = (title or "").strip() or "export"
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", s)
    s = re.sub(r"\s+", "_", s).strip("._") or "export"
    return s[:120]


def _strip_inline_md(text: str) -> str:
    """去掉常见行内标记，保留正文（不做完整 Markdown 解析）。"""
    s = text
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"_(.+?)_", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s


def markdown_to_pdf_bytes(title: str, body_markdown: str) -> bytes:
    try:
        from fpdf import FPDF
    except ImportError as e:
        raise RuntimeError(
            "PDF 导出缺少依赖：请对运行后端的同一解释器执行 `pip install fpdf2`。"
            f" 当前解释器：{sys.executable}"
        ) from e

    md = (body_markdown or "").strip()
    if len(md) > _MAX_MARKDOWN_CHARS:
        md = md[:_MAX_MARKDOWN_CHARS] + "\n\n…（正文过长已截断）"

    font_path = _ensure_font_file()
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    pdf.add_font(_FONT_FAMILY, fname=str(font_path))

    def _write(text: str, *, size: float, line_h: float) -> None:
        pdf.set_font(_FONT_FAMILY, size=size)
        pdf.multi_cell(
            w=pdf.epw,
            h=line_h,
            text=text if text else " ",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    # 标题
    _write((title or "").strip() or "文档", size=18, line_h=10)
    pdf.ln(4)

    # 正文：按行写入；# 标题略放大，其余正文
    in_code = False
    for raw in md.splitlines():
        line = raw.rstrip("\n")
        fence = line.strip().startswith("```")
        if fence:
            in_code = not in_code
            _write(line.strip() or " ", size=9, line_h=5)
            continue

        if in_code:
            _write(line if line else " ", size=9, line_h=5)
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            text = _strip_inline_md(heading.group(2).strip()) or " "
            size = {1: 16, 2: 14, 3: 12}[level]
            pdf.ln(2)
            _write(text, size=size, line_h=size * 0.55)
            continue

        text = _strip_inline_md(line)
        if not text.strip():
            pdf.ln(3)
            continue
        text = re.sub(r"^[-*+]\s+", "- ", text)
        _write(text, size=11, line_h=7)

    out = pdf.output()
    data = bytes(out)
    if not data:
        raise RuntimeError("PDF 字节为空")
    return data


def write_conversation_pdf(title: str, body_markdown: str) -> tuple[str, str]:
    """写入 MEDIA_ROOT/pdf_exports/{uuid}.pdf，返回 (URL 路径, 下载文件名)。"""
    from app.settings import MEDIA_ROOT, MEDIA_URL

    subdir = Path(MEDIA_ROOT) / "pdf_exports"
    subdir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}.pdf"
    path = subdir / name
    path.write_bytes(markdown_to_pdf_bytes(title, body_markdown))

    base = str(MEDIA_URL).rstrip("/")
    return f"{base}/pdf_exports/{name}", f"{_slug_filename(title)}.pdf"
