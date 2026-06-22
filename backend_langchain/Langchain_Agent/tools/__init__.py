"""主智能体与面试大师的工具集。"""

from Langchain_Agent.tools.agent_rag import RAG_TOOLS, get_all_agent_tools, warmup_rag_singletons
from Langchain_Agent.tools.interview_rag import INTERVIEW_RAG_TOOLS, warmup_interview_rag_singletons


def warmup_all_tool_singletons() -> None:
    warmup_rag_singletons()
    warmup_interview_rag_singletons()
