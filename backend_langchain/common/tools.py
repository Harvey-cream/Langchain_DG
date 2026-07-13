"""内置 Agent 工具：Pydantic 入参/出参 schema + LangChain tool 定义。"""
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend_langchain.logger_func import log_exception_event

logger = logging.getLogger(__name__)

PDF_EXPORT_INTERRUPT_KIND = "pdf_export_confirm"
PDF_READY_MARKER = "__PDF_READY__"

PDF_EXPORT_TOOL_MSG_CONFIRM = (
    "[系统] 用户已确认生成 PDF。请结合对话与用户指定范围完成润色后，调用工具 finalize_pdf_export 一次"
    "（title=文档标题，body_markdown=完整 Markdown 成稿）；勿再次调用 confirm_pdf_export。"
)
PDF_EXPORT_TOOL_MSG_CANCEL = (
    "[系统] 用户已取消 PDF 导出，请仅用自然语言友好回复，勿生成 PDF 或下载链接。"
)

_MAX_PDF_TITLE_LEN = 255
_MAX_PDF_BODY_CHARS = 200_000


# =============================================================================
# 入参 Schema（bind_tools / ToolNode 调用前校验）
# =============================================================================


class ConfirmPdfExportInput(BaseModel):
    """PDF 导出人机确认：无业务入参，仅占位生成空 object schema。"""

    model_config = ConfigDict(extra="forbid")


class FinalizePdfExportInput(BaseModel):
    """PDF 成稿导出入参。"""

    title: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PDF_TITLE_LEN,
        description="文档标题，将显示在 PDF 首页。",
    )
    body_markdown: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PDF_BODY_CHARS,
        description="完整 Markdown 成稿（可含 ## 标题、列表、代码围栏）。",
    )

    @field_validator("title", "body_markdown", mode="before")
    @classmethod
    def _strip_non_empty(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if not s:
                raise ValueError("不能为空")
            return s
        return v


# =============================================================================
# 出参 Schema（工具执行后校验，再序列化为 str 给模型）
# =============================================================================


class PdfToolSystemOutput(BaseModel):
    """返回给模型的系统提示行。"""

    message: str = Field(..., min_length=1)

    def to_tool_content(self) -> str:
        return self.message


class PdfReadyToolOutput(BaseModel):
    """PDF 生成成功内部标记（流式层会剥离）。"""

    kind: Literal["ready"] = "ready"
    url: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)

    def to_tool_content(self) -> str:
        return f"{PDF_READY_MARKER}|{self.url}|{self.filename}"


def pdf_export_interrupt_value() -> dict[str, str]:
    return {
        "kind": PDF_EXPORT_INTERRUPT_KIND,
        "message": "是否生成 PDF？请在界面点击「确认」或「取消」（无需在聊天里打字）。",
    }


def _system_tool_output(message: str) -> str:
    return PdfToolSystemOutput(message=message).to_tool_content()


@tool("confirm_pdf_export", args_schema=ConfirmPdfExportInput)
async def confirm_pdf_export() -> str:
    """当用户需要导出/生成 PDF 或正式排版文档时，在输出实质条文前调用本工具一次，等待界面按钮确认。确认后继续 PDF 相关流程；取消则仅自然语言回复。"""
    from langgraph.config import get_stream_writer

    get_stream_writer()({"type": "status", "text": "等待确认 PDF 导出…"})
    approved = interrupt(pdf_export_interrupt_value())
    if approved is True:
        return _system_tool_output(PDF_EXPORT_TOOL_MSG_CONFIRM)
    return _system_tool_output(PDF_EXPORT_TOOL_MSG_CANCEL)


@tool("finalize_pdf_export", args_schema=FinalizePdfExportInput)
async def finalize_pdf_export(title: str, body_markdown: str) -> str:
    """仅在 confirm_pdf_export 已确认后调用一次。将润色后的完整 Markdown 写入 body_markdown，title 为文档标题；成功后浏览器自动下载 PDF。"""
    try:
        payload = FinalizePdfExportInput(title=title, body_markdown=body_markdown)
    except Exception as e:  # noqa: BLE001
        return _system_tool_output(f"[系统] PDF 参数无效：{e}")

    try:
        from human_in_the_loop.pdf_export_render import write_conversation_pdf
        from langgraph.config import get_stream_writer

        rel, fname = write_conversation_pdf(payload.title, payload.body_markdown)
        get_stream_writer()({"type": "pdf_ready", "url": rel, "filename": fname})
        return PdfReadyToolOutput(url=rel, filename=fname).to_tool_content()
    except Exception as e:
        log_exception_event(logger, "finalize_pdf_export_failed", error=str(e))
        hint = str(e).strip()
        if "缺少依赖" in hint or "markdown" in hint.lower():
            return _system_tool_output(
                "[系统] PDF 生成失败：后端未安装 markdown/xhtml2pdf，或 pip 装在了别的 Python 环境。"
                "请对**运行后端的同一 Python 解释器**执行 pip install markdown xhtml2pdf 后重试。"
            )
        return _system_tool_output(
            "[系统] PDF 生成失败，请用自然语言向用户致歉并建议稍后重试，勿伪造下载链接。"
        )


def get_builtin_pdf_tools() -> list:
    """默认内置工具（当前仅 PDF 人机协同）。"""
    return [confirm_pdf_export, finalize_pdf_export]
