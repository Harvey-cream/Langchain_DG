"""LangGraph 人机协同：interrupt 解析与 PDF 工具回传剥离（工具定义见 common.tools）。"""

from __future__ import annotations

import re
from typing import Any

from langgraph.types import Interrupt

from infrastructure.pdf.schema_tools import (
    PDF_EXPORT_TOOL_MSG_CANCEL,
    PDF_EXPORT_TOOL_MSG_CONFIRM,
    PDF_EXPORT_INTERRUPT_KIND,
)

# 向后兼容：外部仍可从 human_loop 导入工具
from infrastructure.pdf.schema_tools import confirm_pdf_export, finalize_pdf_export  # noqa: F401

# 模型常整段复述工具返回值；流式按块到达时用正则兜一层
_SYS_PDF_ECHO = re.compile(r"\[系统\]\s*用户已[^。\n]*PDF[^。\n]*。")

_PDF_READY_LINE_RE = re.compile(r"^\s*__PDF_READY__\|[^\n]+\s*$", re.MULTILINE)


def strip_pdf_export_tool_echo(text: str) -> str:
    """剥离 confirm_pdf_export 回传句，勿进流式/落库可见正文。"""
    if not (text or "").strip():
        return text
    s = _SYS_PDF_ECHO.sub("", text)
    return (
        s.replace(PDF_EXPORT_TOOL_MSG_CONFIRM, "")
        .replace(PDF_EXPORT_TOOL_MSG_CANCEL, "")
    )


def strip_pdf_internal_markers(text: str) -> str:
    """剥离所有人机协同 PDF 工具的内部回传/标记，勿进流式与落库可见正文。"""
    if not (text or "").strip():
        return text
    s = strip_pdf_export_tool_echo(text)
    s = _PDF_READY_LINE_RE.sub("", s)
    return s


def interrupt_payload_from_updates(data: Any) -> dict[str, Any] | None:
    """从 stream_mode=updates 的 payload 中取出 PDF 确认类 interrupt，供 SSE 下发。"""
    if data is None:
        return None
    if isinstance(data, Interrupt):
        val = data.value
        if isinstance(val, dict) and val.get("kind") == PDF_EXPORT_INTERRUPT_KIND:
            return {"kind": val["kind"], "message": val.get("message", "")}
        return None
    if isinstance(data, dict):
        if "__interrupt__" in data:
            return interrupt_payload_from_updates(data["__interrupt__"])
        for v in data.values():
            got = interrupt_payload_from_updates(v)
            if got:
                return got
    if isinstance(data, (list, tuple)):
        for x in data:
            got = interrupt_payload_from_updates(x)
            if got:
                return got
    return None
