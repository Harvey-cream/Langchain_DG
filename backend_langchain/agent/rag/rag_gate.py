"""RAG 门控：轻量 LLM 判断本轮是否检索知识库（非 Agent 工具）。"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from backend_langchain.logger_func import log_info_event, log_warning_event
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)

_GATE_SYSTEM_MAIN = """你是「检索门控器」，只判断本轮是否需要从用户上传的企业/个人文档库做向量检索。
你不回答用户问题，也不改写检索词，只输出 need_rag。

倾向 need_rag=true：
- 用户问某份文档、制度、规范、政策、产品说明、内部材料里「怎么规定 / 有没有写 / 摘要一下」
- 用户要求基于已上传资料做问答、对比、归纳、合规速查、找出处
- 用户说寻找/找一下上传的文件、实习日志、周报、笔记等
- 用户提到「我的文档」「知识库里」「上传的那份」等

倾向 need_rag=false：
- 寒暄、闲聊、感谢、无实质问题
- 用户贴代码/报错要你改（以动手排查为主，不靠文档库）
- 用户要导出 PDF、解析 GitHub/Gitee 仓库链接（走工具流程）
- 明显与用户自有文档无关、且无需查库即可回答的通用闲谈"""

_GATE_SYSTEM_INTERVIEW = """你是「检索门控器」，只判断本轮是否需要从面试题库做向量检索。
你不回答用户问题，也不改写检索词，只输出 need_rag。

倾向 need_rag=true：
- 用户在做面试题、问八股、要标准答法/追问/考点（除非明显是寒暄或导出 PDF）

倾向 need_rag=false：
- 寒暄、闲聊、感谢、无实质问题
- 用户要导出 PDF（走工具流程）
- 明显与题库无关的通用常识"""


class RagGateDecision(BaseModel):
    need_rag: bool = Field(description="本轮是否执行知识库向量检索")


def _fallback_need_rag(mode: str) -> bool:
    """门控失败降级：面试默认检索，知识助手默认不检索。"""
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
    # 文档摘要子 Agent：几乎必定依赖用户库，跳过门控 LLM
    if mode == "main" and (skill_name or "").strip() == "doc_summary":
        log_info_event(
            logger,
            "rag_gate_decision",
            mode=mode,
            skill=skill_name,
            need_rag=True,
            forced=True,
        )
        return True

    is_interview = mode == "interview"
    mode_label = "面试大师" if is_interview else "企业知识库AI助手"
    gate_system = _GATE_SYSTEM_INTERVIEW if is_interview else _GATE_SYSTEM_MAIN
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
            [SystemMessage(content=gate_system), HumanMessage(content=user_msg)]
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
    return bool(decision.need_rag)
