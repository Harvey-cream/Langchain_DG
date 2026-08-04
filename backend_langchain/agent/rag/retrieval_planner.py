"""Retrieval Planner：一次 LLM 合并原 RAG Gate + Query Rewrite。"""
from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field, field_validator

from backend_langchain.logger_func import log_info_event, log_warning_event
from app.settings import rag_config
from config.config import QUERY_REWRITE_MAX_QUESTIONS, get_qwen_chat_model

logger = logging.getLogger(__name__)

# need_rag 规则来自原 rag_gate；问句规则来自原 query_rewrite
_PLANNER_SYSTEM_MAIN = """你是「检索规划器」。根据最近对话与本轮用户消息，判断是否需要从用户上传的企业/个人文档库做向量检索；
若需要，则产出用于向量检索的中文问句。你不回答用户问题。

倾向 need_rag=true：
- 用户问某份文档、制度、规范、政策、产品说明、内部材料里「怎么规定 / 有没有写 / 摘要一下」
- 用户要求基于已上传资料做问答、对比、归纳、合规速查、找出处
- 用户说寻找/找一下上传的文件、实习日志、周报、笔记等
- 用户提到「我的文档」「知识库里」「上传的那份」等

倾向 need_rag=false：
- 寒暄、闲聊、感谢、无实质问题
- 用户贴代码/报错要你改（以动手排查为主，不靠文档库）
- 用户要导出 PDF、解析 GitHub/Gitee 仓库链接（走工具流程）
- 明显与用户自有文档无关、且无需查库即可回答的通用闲谈

若 need_rag=true，search_questions 规则：
1) 输出 1～4 条 search_questions；只问一件事时 1 条即可，复合问题可拆成多条
2) 每条必须是完整问句（是什么/如何/区别/怎么规定/文档里有没有等），不要写成答案
3) 结合上文补全指代（「这个」「它」「那份文件」要落到具体主题或文档名）
4) 每条简洁（建议 15～60 字），不要重复语义
5) 保留专有名词、制度名、产品名、文档标题等关键实体

若 need_rag=false：search_questions 输出空列表。"""

_PLANNER_SYSTEM_INTERVIEW = """你是「检索规划器」。根据最近对话与本轮用户消息，判断是否需要从面试题库做向量检索；
若需要，则产出用于向量检索的中文问句。你不回答用户问题。

倾向 need_rag=true：
- 用户在做面试题、问八股、要标准答法/追问/考点（除非明显是寒暄或导出 PDF）

倾向 need_rag=false：
- 寒暄、闲聊、感谢、无实质问题
- 用户要导出 PDF（走工具流程）
- 明显与题库无关的通用常识

若 need_rag=true，search_questions 规则：
1) 输出 1～4 条 search_questions；只问一件事时 1 条即可，复合问题可拆成多条
2) 每条必须是完整问句（是什么/如何/区别/怎么规定/文档里有没有等），不要写成答案
3) 结合上文补全指代（「这个」「它」「那份文件」要落到具体主题或文档名）
4) 每条简洁（建议 15～60 字），不要重复语义
5) 保留专有名词、制度名、产品名、文档标题等关键实体

若 need_rag=false：search_questions 输出空列表。"""


class RetrievalPlan(BaseModel):
    need_rag: bool = Field(description="本轮是否执行知识库向量检索")
    search_questions: list[str] = Field(
        default_factory=list,
        description="need_rag=true 时 1～4 条检索问句；否则空列表",
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


def _fallback_need_rag(mode: str) -> bool:
    return mode == "interview"


async def plan_retrieval(
    user_input: str,
    *,
    mode: str,
    skill_name: str | None = None,
    recent_dialogue: str = "",
) -> RetrievalPlan:
    """一次 LLM：need_rag + search_questions。"""
    text = (user_input or "").strip()
    if not text:
        return RetrievalPlan(need_rag=False, search_questions=[])

    force_rag = mode == "main" and (skill_name or "").strip() == "doc_summary"
    if force_rag and not _rewrite_enabled():
        log_info_event(
            logger,
            "retrieval_plan",
            mode=mode,
            skill=skill_name,
            need_rag=True,
            forced=True,
            count=1,
        )
        return RetrievalPlan(need_rag=True, search_questions=[text])

    skill = (skill_name or "").strip() or "（未匹配）"
    is_interview = mode == "interview"
    mode_label = "面试大师" if is_interview else "企业知识库AI助手"
    system = _PLANNER_SYSTEM_INTERVIEW if is_interview else _PLANNER_SYSTEM_MAIN
    parts = [f"模式：{mode_label}", f"当前 Skill：{skill}"]
    if (recent_dialogue or "").strip():
        parts.append(f"【最近对话】\n{recent_dialogue.strip()}")
    parts.append(f"【本轮用户】\n{text}")
    user_msg = "\n\n".join(parts)

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_qwen_chat_model(temperature=0.0, streaming=False)
        structured = llm.with_structured_output(RetrievalPlan)
        plan: RetrievalPlan = await structured.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user_msg)]
        )
    except Exception as e:  # noqa: BLE001
        need = True if force_rag else _fallback_need_rag(mode)
        log_warning_event(
            logger,
            "retrieval_plan_failed",
            mode=mode,
            skill=skill_name,
            fallback_need_rag=need,
            error=str(e),
        )
        return RetrievalPlan(
            need_rag=need,
            search_questions=[text] if need else [],
        )

    need = True if force_rag else bool(plan.need_rag)
    questions: list[str] = []
    if need:
        if not _rewrite_enabled():
            questions = [text]
        else:
            questions = _cap_questions(list(plan.search_questions or []))
            if not questions:
                questions = [text]

    log_info_event(
        logger,
        "retrieval_plan",
        mode=mode,
        skill=skill_name,
        need_rag=need,
        forced=force_rag,
        count=len(questions),
    )
    return RetrievalPlan(need_rag=need, search_questions=questions)
