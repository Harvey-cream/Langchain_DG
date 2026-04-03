from __future__ import annotations

from typing import List
from pathlib import Path

from langchain_core.tools import tool
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


def _get_embeddings(model: str) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _get_vectorstore(
    *,
    chroma_dir: str,
    collection_name: str,
    embedding_model: str,
) -> Chroma:
    embeddings = _get_embeddings(embedding_model)
    return Chroma(
        collection_name=collection_name,
        persist_directory=chroma_dir,
        embedding_function=embeddings,
    )


def _format_docs(docs) -> str:
    if not docs:
        return "未检索到相关知识片段。"

    parts: List[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        source_path = meta.get("source_path", "unknown")
        lang = meta.get("lang", "unknown")
        top_section = meta.get("top_section", "unknown")
        chunk_index = meta.get("chunk_index", "unknown")
        content = doc.page_content or ""
        # 控制 tool 输出长度，避免上下文爆炸
        content = content[:1200]

        parts.append(
            f"[{i}] source_path={source_path}, lang={lang}, top_section={top_section}, chunk_index={chunk_index}\n{content}"
        )
    return "\n\n".join(parts)


@tool("chroma_rag_search")
def chroma_rag_search(query: str) -> str:
    """
    从 Chroma 向量库检索与 query 最相关的知识片段，并返回带溯源元数据的结果。

    适用于回答用户问题前的“找资料/做依据”步骤。
    """

    # 默认配置：对应你们入库脚本的默认参数
    # 这里用绝对路径，避免你从不同 cwd 运行导致找不到向量库。
    repo_root = Path(__file__).resolve().parents[2]
    chroma_dir = str(repo_root / "backend_langchain" / "Langchain_knowledge" / "chroma_db")
    collection_name = "vibe_openclaw_md"
    embedding_model = "BAAI/bge-small-zh-v1.5"

    vectorstore = _get_vectorstore(
        chroma_dir=chroma_dir,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )
    # ZERO_SHOT_REACT_DESCRIPTION 只支持单输入工具，因此 k 这里固定写死
    docs = vectorstore.similarity_search(query, k=5)
    return _format_docs(docs)

