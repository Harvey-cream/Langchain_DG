"""文档正文清洗：Markdown / PDF 抽文本去噪（建库向量化前统一走这里）。"""
from __future__ import annotations

import re

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG = re.compile(r"<img\s+[^>]*>", re.IGNORECASE)
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_MD_AUTO_LINK = re.compile(r"<(https?://[^>]+)>")
_HTML_TAG = re.compile(r"<[^>]+>")
_NOISE = re.compile(r"[\uFFFC\u200B\uFEFF\u00a0]+")
_HRULE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_EMPH = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_INLINE_CODE = re.compile(r"`([^`]+)`")


def strip_markdown_images(text: str, *, strip: bool = True) -> str:
    if not strip or not text:
        return text or ""
    text = _MD_IMAGE.sub("", text)
    return _HTML_IMG.sub("", text)


def _strip_line_decorations(line: str) -> str:
    """行内 Markdown 装饰 → 纯文本，保留标题 # 与列表 - 结构。"""
    s = line.strip()
    if not s:
        return ""
    if s.startswith(">"):
        s = s.lstrip(">").strip()
    s = _EMPH.sub(lambda m: m.group(1) or m.group(2) or "", s)
    s = _INLINE_CODE.sub(r"\1", s)
    s = re.sub(r"^[ \t]+", "", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s


def normalize_whitespace(text: str) -> str:
    """
    压空白：多余空行、行尾空格、连续空格。
    嵌入模型对「稀疏正文」不友好，空行过多会稀释语义密度。
    """
    if not text:
        return ""

    out: list[str] = []
    in_fence = False
    prev_blank = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line.strip())
            prev_blank = False
            continue

        if in_fence:
            out.append(line)
            prev_blank = False
            continue

        cleaned = _strip_line_decorations(line)
        if not cleaned:
            if out and not prev_blank:
                out.append("")
                prev_blank = True
            continue

        prev_blank = False
        out.append(cleaned)

    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)


def clean_markdown_text(text: str, *, strip_images: bool = True) -> str:
    """建库用：去图/链接 URL、去 HTML、压空白、弱化 Markdown 装饰。"""
    if not text:
        return ""

    text = strip_markdown_images(text, strip=strip_images)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_AUTO_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _HRULE.sub("", text)
    text = _NOISE.sub(" ", text)
    text = normalize_whitespace(text)
    return text.strip()


def clean_pdf_text(text: str) -> str:
    if not text:
        return ""
    return clean_markdown_text(text, strip_images=True)
