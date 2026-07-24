"""文档正文清洗：按格式分流（Markdown / PDF / 纯文本）。"""
from __future__ import annotations

import re
import unicodedata

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG = re.compile(r"<img\s+[^>]*>", re.IGNORECASE)
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_MD_AUTO_LINK = re.compile(r"<(https?://[^>]+)>")
_HTML_TAG = re.compile(r"<[^>]+>")
_NOISE = re.compile(r"[\uFFFC\u200B\uFEFF\u00a0]+")
_HRULE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_EMPH = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_FENCE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_SPACED_LATIN = re.compile(r"\b(?:[A-Za-z]\s+){1,}[A-Za-z]\b")
_QUESTION_LINE = re.compile(r"^(?:\d+[、.)）]\s*)?.{4,240}[？?]\s*$")


def strip_markdown_images(text: str, *, strip: bool = True) -> str:
    if not strip or not text:
        return text or ""
    text = _MD_IMAGE.sub("", text)
    return _HTML_IMG.sub("", text)


def _strip_line_decorations(line: str) -> str:
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


def _clean_markdown_outside_fences(segment: str, *, strip_images: bool) -> str:
    text = strip_markdown_images(segment, strip=strip_images)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_AUTO_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _HRULE.sub("", text)
    text = _NOISE.sub(" ", text)
    return text


def normalize_whitespace(text: str) -> str:
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


def normalize_plain_whitespace(text: str) -> str:
    """纯文本：只压空白，不剥 Markdown/HTML。"""
    if not text:
        return ""
    text = _NOISE.sub(" ", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    prev_blank = False
    for line in lines:
        if not line.strip():
            if out and not prev_blank:
                out.append("")
                prev_blank = True
            continue
        prev_blank = False
        out.append(line)
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def clean_markdown_text(text: str, *, strip_images: bool = True) -> str:
    """Markdown：围栏内原样保留（避免删掉 <groupId> 等代码）。"""
    if not text:
        return ""

    parts: list[str] = []
    last = 0
    for m in _FENCE_BLOCK.finditer(text):
        if m.start() > last:
            parts.append(_clean_markdown_outside_fences(text[last : m.start()], strip_images=strip_images))
        parts.append(m.group(0))
        last = m.end()
    if last < len(text):
        parts.append(_clean_markdown_outside_fences(text[last:], strip_images=strip_images))

    return normalize_whitespace("".join(parts)).strip()


def clean_plain_text(text: str) -> str:
    """txt / json / requirements 等：勿当 Markdown 清洗。"""
    if not text:
        return ""
    text = _NOISE.sub(" ", text)
    return normalize_plain_whitespace(text).strip()


def _normalize_cjk(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _fix_spaced_latin_words(text: str) -> str:
    def _collapse(m: re.Match[str]) -> str:
        return re.sub(r"\s+", "", m.group(0))

    return _SPACED_LATIN.sub(_collapse, text)


def clean_pdf_text(text: str) -> str:
    """PDF 专用：CJK 规范化、拉丁字母粘连修复、空白与噪声清理。"""
    if not text:
        return ""
    text = _normalize_cjk(text)
    text = _fix_spaced_latin_words(text)
    text = _NOISE.sub(" ", text)
    return normalize_plain_whitespace(text).strip()


def is_pdf_question_line(line: str) -> bool:
    s = (line or "").strip()
    if not s or len(s) < 6:
        return False
    return bool(_QUESTION_LINE.match(s))


def split_pdf_text_by_questions(text: str) -> list[str]:
    """按「问句行」切分为语义块（面试 PDF 等）。"""
    text = (text or "").strip()
    if not text:
        return []

    lines = text.splitlines()
    sections: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        block = "\n".join(buf).strip()
        if block:
            sections.append(block)
        buf.clear()

    for line in lines:
        if is_pdf_question_line(line) and buf:
            flush()
        buf.append(line)
    flush()

    if len(sections) <= 1:
        return [text]
    return sections
