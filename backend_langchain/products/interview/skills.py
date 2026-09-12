"""面试 Agent 线 Skill 目录（业务归属本产品线，引擎见 infrastructure.rag.skill_router）。"""
from __future__ import annotations

from infrastructure.rag.skill_router import SkillSpec

INTERVIEW_SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec(
        name="interview_mock",
        when="面试问答、追问演练、答题优化",
        output_schema="考点 -> 标准答法 -> 高频追问 -> 易错点",
        prototypes=(
            "用户在准备技术面试，需要模拟问答与追问演练。",
            "用户希望优化面试表达，给出标准答法与易错点。",
        ),
    ),
    SkillSpec(
        name="learning_planner",
        when="求职学习路线、冲刺计划、项目补齐",
        output_schema="目标拆分 -> 周任务 -> 里程碑 -> 复盘",
        prototypes=(
            "用户要制定面试准备计划、冲刺节奏和里程碑。",
            "用户希望拆解周任务并给出复盘节奏。",
        ),
    ),
    SkillSpec(
        name="knowledge_qa",
        when="题库/知识库条目的解释、对比与归纳",
        output_schema="问题澄清 -> 命中知识点 -> 答案总结 -> 延伸建议",
        prototypes=(
            "用户询问题库知识点定义、原理、区别与归纳。",
            "用户问 Java、Vue、大模型等面试知识点是什么或怎么理解。",
        ),
    ),
    SkillSpec(
        name="document_export",
        when="用户要把面试准备内容导出为 PDF；含代码题解答、手写代码、算法步骤整理成 PDF",
        output_schema="人机协同：先 confirm_pdf_export；确认后尽快 finalize_pdf_export；整理已有内容保质，勿无故扩写；确认前勿声称已生成文件",
        prototypes=(
            "用户希望把面试题总结、错题本或准备清单导出成 PDF。",
            "用户要下载打印版面试材料、PDF 版复习大纲。",
            "用户说整理成文档发我、做成 PDF。",
            "用户要把代码题答案、手写代码、算法实现过程导出或打印成 PDF。",
        ),
        anti_prototypes=(
            "用户只在模拟面试问答，未要求导出或 PDF。",
            "用户只问某题怎么答、知识点是什么，不要求文档或下载。",
        ),
    ),
)
