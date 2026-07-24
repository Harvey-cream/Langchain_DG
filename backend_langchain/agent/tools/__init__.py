"""工具集：按 Agent 线分文件，本包仅做聚合导出。"""

from agent.tools.interview import get_interview_tools
from agent.tools.knowledge import (
    get_all_agent_tools,
    get_summary_tools,
    warmup_knowledge_stores,
)

__all__ = [
    "get_all_agent_tools",
    "get_interview_tools",
    "get_summary_tools",
    "warmup_all_tool_singletons",
    "warmup_knowledge_stores",
]


def warmup_all_tool_singletons() -> None:
    warmup_knowledge_stores()
