from __future__ import annotations

import logging
import os
import threading
from typing import List
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from langchain_chroma import Chroma

from common.embedding import get_embedding_model

logger = logging.getLogger(__name__)
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# 与 Scripts/build_md_knowledge.py 一致：同一 collection 名，数据按子目录隔离。
# 检索时：Chroma(persist_directory=.../chroma_db/<子目录名>) 只读该目录下的向量集合。
# 子目录名必须与 build_md_knowledge.DEFAULT_BASES 里第三列一致，否则工具会指向错误库或报「目录不存在」。
_COLLECTION_NAME = "md_knowledge"
_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
_TOP_K = 5

# 各工具对应的 Chroma 持久化子目录（相对 …/Langchain_knowledge/chroma_db/）
_STORE_AI_PROGRAMMING = "AI_programming"
_STORE_OPENCLAW = "Openclaw"
_STORE_VIBE_CODING = "Vibecoding"
_STORE_LEARNING_INTERVIEW = "Learn_programing"

# 四套库子目录（与上方常量一致，供启动预热遍历）
_CHROMA_SUBDIRS: tuple[str, ...] = (
    _STORE_AI_PROGRAMMING,
    _STORE_OPENCLAW,
    _STORE_VIBE_CODING,
    _STORE_LEARNING_INTERVIEW,
)

# 每个向量子目录只建一次 Chroma，避免每次工具调用都重新打开库与触发遥测
_chroma_store_cache: dict[str, Chroma] = {}
_chroma_lock = threading.Lock()


def _chroma_root() -> Path:
    """项目内向量根目录：…/Langchain_knowledge/chroma_db"""
    return Path(__file__).resolve().parents[2] / "backend_langchain" / "Langchain_knowledge" / "chroma_db"


def _get_embeddings() -> Embeddings:
    """统一从 common.embedding 获取单例模型。"""
    return get_embedding_model(_EMBEDDING_MODEL, device="cpu", normalize_embeddings=True, batch_size=32)


def _get_chroma_store(persist_subdir: str) -> Chroma | None:
    """同一 persist 子目录复用 Chroma 实例；嵌入模型仍由 _get_embeddings() 单例持有。"""
    global _chroma_store_cache
    root = _chroma_root() / persist_subdir
    if not root.is_dir():
        return None
    if persist_subdir not in _chroma_store_cache:
        with _chroma_lock:
            if persist_subdir not in _chroma_store_cache:
                _chroma_store_cache[persist_subdir] = Chroma(
                    collection_name=_COLLECTION_NAME,
                    persist_directory=str(root),
                    embedding_function=_get_embeddings(),
                )
    return _chroma_store_cache[persist_subdir]


def warmup_rag_singletons() -> None:
    """
    进程内全局单例预热：嵌入模型 + 各 persist 子目录的 Chroma 各只构建一次。
    应在 Django 启动时调用一次；同一进程内后续请求复用同一批实例。

    注意：每次「重启后端进程」（runserver 重启、gunicorn worker 重启）都会重新加载权重，无法跨进程共享内存。
    可用环境变量 SKIP_RAG_STARTUP_WARMUP=1 跳过启动预热（测试/migrate 等）。
    """
    _get_embeddings()
    for sub in _CHROMA_SUBDIRS:
        _get_chroma_store(sub)
    try:
        from MCP.mcp_multiserver import load_mcp_tools_once

        load_mcp_tools_once()
    except Exception:
        logger.exception("warmup_rag_singletons: MCP 工具预加载失败")


def _format_docs(docs) -> str:
    if not docs:
        return "未检索到相关知识片段。"

    parts: List[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        kb = (meta.get("knowledge_base") or "资料").strip()
        content = (doc.page_content or "").strip()[:1200]
        # 勿输出 knowledge_base=/source_path= 等机器行，避免模型照抄进用户可见正文
        parts.append(f"【片段{i}·{kb}】\n{content}")
    return "\n\n".join(parts)


def _rag_similarity_search(persist_subdir: str, query: str) -> str:
    """在单个向量库目录内检索：persist_subdir 为 chroma_db 下的文件夹名。"""
    vs = _get_chroma_store(persist_subdir)
    if vs is None:
        root = _chroma_root() / persist_subdir
        return (
            f"向量库目录不存在或未构建：{root}。"
            f"请在 backend_langchain 下运行：python Scripts/build_md_knowledge.py"
        )
    docs = vs.similarity_search(query.strip(), k=_TOP_K)
    return _format_docs(docs)


@tool("rag_ai_programming")
def rag_ai_programming(query: str) -> str:
    """检索「AI 编程工具与实战」向量知识库。

    适用场景：各类 AI 编程工具选型、IDE/插件、命令行工具、智能体平台、与本知识域相关的实操与对比。
    输入：用自然语言描述要查找的主题或问题（中文或英文均可）。
    输出：带溯源字段的若干文本片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_AI_PROGRAMMING, query)


@tool("rag_openclaw")
def rag_openclaw(query: str) -> str:
    """检索「OpenClaw 保姆级教程」向量知识库。

    适用场景：OpenClaw 安装、配置、部署、使用流程、排错及教程内步骤性问题。
    输入：用自然语言描述要查找的主题或问题。
    输出：带溯源字段的若干文本片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_OPENCLAW, query)


@tool("rag_vibe_coding")
def rag_vibe_coding(query: str) -> str:
    """检索「Vibe Coding 零基础教程」向量知识库。

    适用场景：Vibe Coding 概念、项目流程、全栈/小程序/AI 应用开发、经验技巧与最佳实践等本教程覆盖内容。
    输入：用自然语言描述要查找的主题或问题。
    输出：带溯源字段的若干文本片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_VIBE_CODING, query)


@tool("rag_learning_interview")
def rag_learning_interview(query: str) -> str:
    """检索「编程学习路线与面试」向量知识库。

    适用场景：学习路线、面试准备、简历与刷题、AI 时代技能、团队规范、MCP 等与该知识域相关的条目。
    输入：用自然语言描述要查找的主题或问题。
    输出：带溯源字段的若干文本片段；若无命中则说明未检索到。
    """
    return _rag_similarity_search(_STORE_LEARNING_INTERVIEW, query)


# 内置工具（知识库）；仓库/企业能力通过 MCP_SERVERS_* 配置的 MultiServer 工具注入，见 get_all_agent_tools()
RAG_TOOLS = [
    rag_ai_programming,
    rag_openclaw,
    rag_vibe_coding,
    rag_learning_interview,
]


def _is_tavily_tool(tool_obj: object) -> bool:
    name = str(getattr(tool_obj, "name", "") or "").strip().lower()
    return "tavily" in name or "web_search" in name


def get_all_agent_tools(*, enable_web_search: bool = False) -> list:
    """内置 RAG 工具 + 人机协同工具 + MCP 工具（按 enable_web_search 控制 Tavily 可用性）。"""
    from human_in_the_loop.human_loop import confirm_pdf_export, finalize_pdf_export
    from MCP.mcp_multiserver import load_mcp_tools_once

    mcp_tools = list(load_mcp_tools_once())
    if not enable_web_search:
        mcp_tools = [t for t in mcp_tools if not _is_tavily_tool(t)]
    return list(RAG_TOOLS) + [confirm_pdf_export, finalize_pdf_export] + mcp_tools
