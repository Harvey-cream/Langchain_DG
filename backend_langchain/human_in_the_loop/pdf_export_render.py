"""Markdown → HTML → PDF（xhtml2pdf），供 finalize_pdf_export 工具落盘并通过 MEDIA 提供下载。"""

from __future__ import annotations

import html
import logging
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_MAX_MARKDOWN_CHARS = 200_000


def _try_register_ttf(pdfmetrics: Any, TTFont: Any, path: Path, subfont_index: int | None) -> bool:
    """尝试注册为 PdfExportFont；成功返回 True。"""
    try:
        if subfont_index is None:
            pdfmetrics.registerFont(TTFont("PdfExportFont", str(path)))
        else:
            pdfmetrics.registerFont(TTFont("PdfExportFont", str(path), subfontIndex=subfont_index))
        return True
    except Exception:
        return False


def _register_cjk_font() -> str:
    """注册可嵌入 PDF 的中文字体，返回 CSS font-family 名；失败则用 Helvetica（中文会成方框）。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "PdfExportFont" in pdfmetrics.getRegisteredFontNames():
        return "PdfExportFont"

    env_path = (os.environ.get("PDF_EXPORT_FONT") or "").strip()
    candidates: list[tuple[Path, int | None]] = []

    if env_path:
        p = Path(env_path)
        if p.is_file():
            # 单字体文件：无 subfont；.ttc 可尝试 0/1
            if p.suffix.lower() == ".ttc":
                candidates.append((p, 0))
                candidates.append((p, 1))
            else:
                candidates.append((p, None))

    if os.name == "nt":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for name, idx in (
            ("msyh.ttc", 0),
            ("msyh.ttc", 1),
            ("msyhl.ttc", 0),
            ("simsun.ttc", 0),
            ("simsun.ttc", 1),
            ("simhei.ttf", None),
            ("msyhbd.ttc", 0),
        ):
            candidates.append((windir / name, idx))
    else:
        for cand in (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ):
            cp = Path(cand)
            if cp.is_file():
                candidates.append((cp, 0))
                candidates.append((cp, 1))
                break

    for path, sub_idx in candidates:
        if not path.is_file():
            continue
        if _try_register_ttf(pdfmetrics, TTFont, path, sub_idx):
            logger.info("PDF 导出：已注册中文字体 %s (subfont=%s)", path, sub_idx)
            return "PdfExportFont"

    logger.warning(
        "PDF 导出：未注册任何中文字体，中文将显示为方框；请设置 PDF_EXPORT_FONT 为 .ttf/.ttc 完整路径"
    )
    return "Helvetica"


def _slug_filename(title: str) -> str:
    s = (title or "").strip() or "export"
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", s)
    s = re.sub(r"\s+", "_", s).strip("._") or "export"
    return s[:120]


def markdown_to_pdf_bytes(title: str, body_markdown: str) -> bytes:
    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError(
            "PDF 导出缺少依赖：请在**启动 Django 的同一 Python 解释器**中执行 "
            "`pip install markdown xhtml2pdf`（或 `pip install -r requirements.txt`）。"
            f" 当前解释器：{sys.executable}"
        ) from e

    md = (body_markdown or "").strip()
    if len(md) > _MAX_MARKDOWN_CHARS:
        md = md[:_MAX_MARKDOWN_CHARS] + "\n\n…（正文过长已截断）"

    font = _register_cjk_font()
    # xhtml2pdf 对继承字体不稳定：强制全文（含 markdown 生成的 p/li/pre）使用同一套可显示中文的字体。
    # 勿对 pre/code 单独指定 DejaVu 等西文字体，否则中文代码/正文会变成方框。
    body_html = markdown.markdown(
        md,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html",
    )
    safe_title = html.escape((title or "").strip() or "文档", quote=True)
    doc_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
@page {{ size: A4; margin: 18mm; }}
html, body, div, p, span, li, ol, ul, td, th, h1, h2, h3, h4, h5, h6, blockquote, strong, em, a, pre, code, table, thead, tbody {{
  font-family: {font}, Arial, Helvetica, sans-serif !important;
}}
body {{ font-size: 11pt; line-height: 1.45; color: #222; }}
h1 {{ font-size: 18pt; margin: 0 0 12pt 0; padding-bottom: 8pt; border-bottom: 1px solid #ccc; }}
h2 {{ font-size: 14pt; margin: 16pt 0 8pt 0; }}
h3 {{ font-size: 12pt; margin: 12pt 0 6pt 0; }}
pre, code {{ font-size: 9.5pt; }}
pre {{ background: #f6f8fa; padding: 8pt; border-radius: 4pt; white-space: pre-wrap; word-break: break-word; }}
code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 2px; }}
ul, ol {{ margin: 6pt 0; padding-left: 22pt; }}
blockquote {{ margin: 8pt 0; padding-left: 12pt; border-left: 3pt solid #ddd; color: #444; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0; }}
th, td {{ border: 1px solid #ccc; padding: 4pt 6pt; font-size: 10pt; }}
</style></head><body>
<h1>{safe_title}</h1>
{body_html}
</body></html>"""

    out = BytesIO()
    pdf = pisa.CreatePDF(
        src=BytesIO(doc_html.encode("utf-8")),
        dest=out,
        encoding="utf-8",
    )
    if pdf.err:
        raise RuntimeError("xhtml2pdf 生成失败")
    data = out.getvalue()
    if not data:
        raise RuntimeError("PDF 字节为空")
    return data


def write_conversation_pdf(title: str, body_markdown: str) -> tuple[str, str]:
    """
    写入 MEDIA_ROOT/pdf_exports/{uuid}.pdf，返回 (相对站点的 URL 路径, 建议下载文件名)。
    URL 形如 /media/pdf_exports/....pdf

    正文仅来自工具参数 body_markdown（由模型根据对话组织），不从数据库拉取会话内容。
    """
    from django.conf import settings

    media_root = Path(settings.MEDIA_ROOT)
    subdir = media_root / "pdf_exports"
    subdir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4().hex}.pdf"
    path = subdir / name
    path.write_bytes(markdown_to_pdf_bytes(title, body_markdown))

    base = str(settings.MEDIA_URL).rstrip("/")
    rel_url = f"{base}/pdf_exports/{name}"
    download_name = f"{_slug_filename(title)}.pdf"
    return rel_url, download_name

