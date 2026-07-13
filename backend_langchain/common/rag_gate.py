"""RAG 门控：轻量 LLM 判断本轮是否检索知识库（非 Agent 工具）。"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend_langchain.logger_func import log_info_event, log_warning_event
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

_GATE_SYSTEM = """你是「检索门控器」，只判断本轮是否需要从项目知识库做向量检索。
你不回答用户问题，也不改写检索词，只输出 need_rag。

倾向 need_rag=true：
- 用户问教程/概念/原理/对比/归纳，且与项目沉淀（AI 编程、Vibe Coding、OpenClaw、学习路线、面试题库）相关
- 面试模式下：用户在做面试题、问八股、要标准答法/追问/考点（除非明显是寒暄或导出 PDF）

倾向 need_rag=false：
- 寒暄、闲聊、感谢、无实质问题
- 用户贴代码/报错要你改（以动手排查为主，不靠知识库）
- 用户要导出 PDF、解析 GitHub/Gitee 仓库链接（走工具流程）
- 明显与项目知识库无关的通用常识"""


class RagGateDecision(BaseModel):
    need_rag: bool = Field(description="本轮是否执行知识库向量检索")


def _fallback_need_rag(mode: str) -> bool:
    """门控失败降级：面试默认检索(B)，主对话默认不检索。"""
    return mode == "interview"


async def decide_rag_gate(
    user_input: str,
    *,
    mode: str,
    skill_name: str | None = None,
) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False

    skill = (skill_name or "").strip() or "（未匹配）"
    mode_label = "面试大师" if mode == "interview" else "主对话"
    user_msg = (
        f"模式：{mode_label}\n"
        f"当前 Skill：{skill}\n"
        f"用户本轮消息：\n{text}"
    )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_qwen_chat_model(temperature=0.0, streaming=False)
        structured = llm.with_structured_output(RagGateDecision)
        decision: RagGateDecision = await structured.ainvoke(
            [SystemMessage(content=_GATE_SYSTEM), HumanMessage(content=user_msg)]
        )
    except Exception as e:  # noqa: BLE001
        need = _fallback_need_rag(mode)
        log_warning_event(
            logger,
            "rag_gate_failed",
            mode=mode,
            skill=skill_name,
            fallback_need_rag=need,
            error=str(e),
        )
        return need

    log_info_event(
        logger,
        "rag_gate_decision",
        mode=mode,
        skill=skill_name,
        need_rag=decision.need_rag,
    )
    return decision.need_rag
