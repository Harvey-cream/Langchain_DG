"""面试 Agent 线工具集（与知识库线隔离；当前仅 PDF HITL）。"""
from __future__ import annotations


def get_interview_tools() -> list:
    from common.tools import get_builtin_pdf_tools

    return get_builtin_pdf_tools()
