"""主智能体与面试大师的工具集。"""

from Langchain_Agent.tools.knowledge import get_all_agent_tools, get_interview_tools, warmup_knowledge_stores


def warmup_all_tool_singletons() -> None:
    warmup_knowledge_stores()
