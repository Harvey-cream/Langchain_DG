"""LangGraph 人机协同：PDF 导出意图确认（interrupt + Command.resume）与成稿导出工具。"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from langchain_core.tools import tool
from langgraph.types import Interrupt, interrupt
from backend_langchain.logger_func import log_exception_event

logger = logging.getLogger(__name__)

PDF_EXPORT_INTERRUPT_KIND = "pdf_export_confirm"
PDF_READY_MARKER = "__PDF_READY__"

# 工具返回给模型的内部提示；流式/落库需剥离，避免当作用户可见正文
PDF_EXPORT_TOOL_MSG_CONFIRM = (
    "[系统] 用户已确认生成 PDF。请结合对话与用户指定范围完成润色后，调用工具 finalize_pdf_export 一次"
    "（title=文档标题，body_markdown=完整 Markdown 成稿）；勿再次调用 confirm_pdf_export。"
)
PDF_EXPORT_TOOL_MSG_CANCEL = (
    "[系统] 用户已取消 PDF 导出，请仅用自然语言友好回复，勿生成 PDF 或下载链接。"
)

# 模型常整段复述工具返回值；流式按块到达时用正则兜一层
_SYS_PDF_ECHO = re.compile(r"\[系统\]\s*用户已[^。\n]*PDF[^。\n]*。")


def strip_pdf_export_tool_echo(text: str) -> str:
    """剥离 confirm_pdf_export 回传句，勿进流式/落库可见正文。"""
    if not (text or "").strip():
        return text
    s = _SYS_PDF_ECHO.sub("", text)
    return (
        s.replace(PDF_EXPORT_TOOL_MSG_CONFIRM, "")
        .replace(PDF_EXPORT_TOOL_MSG_CANCEL, "")
    )


# finalize_pdf_export 内部标记；勿展示给用户
_PDF_READY_LINE_RE = re.compile(r"^\s*__PDF_READY__\|[^\n]+\s*$", re.MULTILINE)


def strip_pdf_internal_markers(text: str) -> str:
    """剥离所有人机协同 PDF 工具的内部回传/标记，勿进流式与落库可见正文。"""
    if not (text or "").strip():
        return text
    s = strip_pdf_export_tool_echo(text)
    s = _PDF_READY_LINE_RE.sub("", s)
    return s


def pdf_export_interrupt_value() -> dict[str, str]:
    return {
        "kind": PDF_EXPORT_INTERRUPT_KIND,
        "message": "是否生成 PDF？请在界面点击「确认」或「取消」（无需在聊天里打字）。",
    }


@tool("confirm_pdf_export")
def confirm_pdf_export() -> str:
    """当用户需要导出/生成 PDF 或正式排版文档时，在输出实质条文前调用本工具一次，等待界面按钮确认。确认后继续 PDF 相关流程；取消则仅自然语言回复。"""
    approved = interrupt(pdf_export_interrupt_value())
    if approved is True:
        return PDF_EXPORT_TOOL_MSG_CONFIRM
    return PDF_EXPORT_TOOL_MSG_CANCEL


@tool("finalize_pdf_export")
def finalize_pdf_export(title: str, body_markdown: str) -> str:
    """仅在工具 confirm_pdf_export 已返回「用户已确认」之后调用一次（勿重复调用）。根据用户指定范围与对话上下文，先在心里完成润色与排版，将最终交付用的完整 Markdown 写入 body_markdown（可含标题层级、列表、代码围栏）；title 为文档标题。调用成功后浏览器将自动下载 PDF，你只需用一两句自然话告知用户已可下载，勿复述工具返回值或任何 __ 开头的内部标记。"""
    try:
        from human_in_the_loop.pdf_export_render import write_conversation_pdf

        rel, fname = write_conversation_pdf(title, body_markdown)
        return f"{PDF_READY_MARKER}|{rel}|{fname}"
    except Exception as e:
        log_exception_event(logger, "finalize_pdf_export_failed")
        hint = str(e).strip()
        if "缺少依赖" in hint or "markdown" in hint.lower():
            return (
                "[系统] PDF 生成失败：后端未安装 markdown/xhtml2pdf，或 pip 装在了别的 Python 环境。"
                "请对**运行 runserver 用的解释器**执行 pip install markdown xhtml2pdf 后重试。"
            )
        return "[系统] PDF 生成失败，请用自然语言向用户致歉并建议稍后重试，勿伪造下载链接。"


def _tool_content_to_str(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "text" in block:
                    parts.append(str(block["text"]))
        return "".join(parts)
    return str(content)


def _iter_tool_message_texts(data: Any) -> Iterator[str]:
    from langchain_core.messages import ToolMessage

    if isinstance(data, ToolMessage):
        yield _tool_content_to_str(data.content)
        return
    if isinstance(data, dict):
        for v in data.values():
            yield from _iter_tool_message_texts(v)
    elif isinstance(data, (list, tuple)):
        for x in data:
            yield from _iter_tool_message_texts(x)


def pdf_ready_payload_from_updates(data: Any) -> dict[str, str] | None:
    """从 stream_mode=updates 中解析 finalize_pdf_export 的成功回传，供 SSE 触发浏览器下载。"""
    prefix = f"{PDF_READY_MARKER}|"
    for text in _iter_tool_message_texts(data):
        if not text or PDF_READY_MARKER not in text:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith(prefix):
                continue
            rest = line[len(prefix) :]
            url, _sep, filename = rest.rpartition("|")
            if url and filename:
                return {"url": url, "filename": filename}
    return None


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

