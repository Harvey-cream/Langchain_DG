"""企业知识库线：子 Agent 定义（供总控 LLM 分诊，与面试线隔离）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KnowledgeAgentId = Literal["doc_summary", "knowledge_qa"]


@dataclass(frozen=True)
class KnowledgeSubAgentDef:
    """子 Agent 说明书：总控只读这些字段做路由，不执行业务。"""

    id: KnowledgeAgentId
    title: str
    description: str
    when_to_use: str
    when_not_to_use: str


DOC_SUMMARY_AGENT = KnowledgeSubAgentDef(
    id="doc_summary",
    title="文档摘要 Agent",
    description="对用户已上传并入库的文档做摘要、导读、要点提炼与内容概览。",
    when_to_use=(
        "用户要总结/概括/导读/提炼某份或某批已上传文档的主要内容；"
        "需要整份材料的结构概览，而不是追问某一具体条款怎么执行。"
    ),
    when_not_to_use=(
        "用户在问某一制度/条款如何规定、怎么办、有没有某句话；"
        "要对比差异、查找出处、导出 PDF、或解析 GitHub/Gitee 仓库。"
    ),
)

KNOWLEDGE_QA_AGENT = KnowledgeSubAgentDef(
    id="knowledge_qa",
    title="知识问答 Agent",
    description=(
        "基于用户上传文档做检索问答、查找材料、对比与出处说明；"
        "并处理导出 PDF、解析代码仓库等工具类请求。"
    ),
    when_to_use=(
        "用户基于上传文档提问、查条款、找文件内容、对比材料；"
        "明确要求导出 PDF；提供了仓库链接要解析；"
        "寒暄闲聊或其它未明确要求整篇摘要的请求（默认兜底）。"
    ),
    when_not_to_use=(
        "用户明确只要整份文档的摘要/导读/要点提炼，且没有追问具体条款。"
    ),
)

KNOWLEDGE_SUB_AGENTS: tuple[KnowledgeSubAgentDef, ...] = (
    DOC_SUMMARY_AGENT,
    KNOWLEDGE_QA_AGENT,
)


def render_sub_agents_for_router(agents: tuple[KnowledgeSubAgentDef, ...] = KNOWLEDGE_SUB_AGENTS) -> str:
    """拼进总控 system prompt，供 LLM 选择 agent_id。"""
    blocks: list[str] = []
    for a in agents:
        blocks.append(
            f"### {a.id}（{a.title}）\n"
            f"- 职责：{a.description}\n"
            f"- 应该使用：{a.when_to_use}\n"
            f"- 不要使用：{a.when_not_to_use}"
        )
    return "\n\n".join(blocks)
