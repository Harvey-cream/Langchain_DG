"""Cascade Router：高置信规则短路，否则交 Supervisor LLM。"""
from __future__ import annotations

import re

from agent.graphs.knowledge_subagents import KnowledgeAgentId

# 仓库 / 导出 → knowledge_qa
_REPO = re.compile(
    r"(https?://)?(github\.com|gitee\.com)/[\w.-]+/[\w.-]+|解析仓库|分析.*仓库|repo\b",
    re.I,
)
_PDF_EXPORT = re.compile(
    r"(导出\s*PDF|生成.*PDF|下载.*PDF|打印版|正式文档|导出成文档)",
    re.I,
)

# 摘要意图
_SUMMARY = re.compile(
    r"(摘要|总结|概括|导读|要点提炼|内容概览|总结一下|概括一下)",
    re.I,
)
# 与摘要冲突 → 不短路
_CLAUSE = re.compile(
    r"(怎么办|怎么规定|有没有|第\s*\d+\s*条|条款|对比|差异|出处|如何执行)",
    re.I,
)

_CHITCHAT = re.compile(
    r"^(好的?|嗯+|哦+|继续|谢谢|感谢|收到|ok|okay|yes|no|是的?|不是|"
    r"可以|行|加油|你好|在吗|嗨|hello|hi)[\s!！。.~…]*$",
    re.I,
)


def try_cascade_route(user_text: str) -> KnowledgeAgentId | None:
    """高置信则返回 agent_id；否则 None（走 Supervisor LLM）。"""
    text = (user_text or "").strip()
    if not text:
        return "knowledge_qa"

    if _REPO.search(text) or _PDF_EXPORT.search(text):
        return "knowledge_qa"

    if _SUMMARY.search(text) and not _CLAUSE.search(text) and not _REPO.search(text):
        if not _PDF_EXPORT.search(text):
            return "doc_summary"

    if _CHITCHAT.match(text):
        return "knowledge_qa"

    return None
