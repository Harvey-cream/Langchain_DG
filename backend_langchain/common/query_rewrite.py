"""检索问句改写：结合最近对话，产出 1～N 条检索用问句。"""
from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field, field_validator

from backend_langchain.logger_func import log_info_event, log_warning_event
from app.settings import rag_config
from config.config import QUERY_REWRITE_MAX_QUESTIONS, get_qwen_chat_model

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM = """你是「检索问句改写器」。根据最近对话与本轮用户消息，产出用于向量检索的中文问句。
你不回答问题。

规则：
1) 输出 1～4 条 search_questions；只问一件事时 1 条即可，复合问题可拆成多条
2) 每条必须是完整问句（是什么/如何/区别/怎么规定/文档里有没有等），不要写成答案
3) 结合上文补全指代（「这个」「它」「那份文件」要落到具体主题或文档名）
4) 每条简洁（建议 15～60 字），不要重复语义
5) 保留专有名词、制度名、产品名、文档标题等关键实体"""


class RewriteOutput(BaseModel):
    search_questions: list[str] = Field(
        min_length=1,
        description="1～4 条检索问句",
    )

    @field_validator("search_questions", mode="before")
    @classmethod
    def _normalize_questions(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for item in v:
            s = str(item or "").strip()
            if s and s not in out:
                out.append(s)
        return out


def _rewrite_enabled() -> bool:
    raw = os.getenv("QUERY_REWRITE_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return bool(rag_config().get("query_rewrite_enabled", True))


def _cap_questions(questions: list[str]) -> list[str]:
    cap = max(1, QUERY_REWRITE_MAX_QUESTIONS)
    return questions[:cap]


async def rewrite_search_queries(
    user_input: str,
    *,
    mode: str,
    skill_name: str | None = None,
    recent_dialogue: str = "",
) -> list[str]:
    text = (user_input or "").strip()
    if not text:
        return []

    if not _rewrite_enabled():
        return [text]

    skill = (skill_name or "").strip() or "（未匹配）"
    mode_label = "面试大师" if mode == "interview" else "企业知识库AI助手"
    parts = [f"模式：{mode_label}", f"当前 Skill：{skill}"]
    if (recent_dialogue or "").strip():
        parts.append(f"【最近对话】\n{recent_dialogue.strip()}")
    parts.append(f"【本轮用户】\n{text}")
    user_msg = "\n\n".join(parts)

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_qwen_chat_model(temperature=0.0, streaming=False)
        structured = llm.with_structured_output(RewriteOutput)
        out: RewriteOutput = await structured.ainvoke(
            [SystemMessage(content=_REWRITE_SYSTEM), HumanMessage(content=user_msg)]
        )
        questions = _cap_questions(out.search_questions)
        if not questions:
            return [text]
    except Exception as e:  # noqa: BLE001
        log_warning_event(logger, "query_rewrite_failed", error=str(e))
        return [text]

    log_info_event(
        logger,
        "query_rewrite_ok",
        mode=mode,
        skill=skill_name,
        count=len(questions),
    )
    return questions
