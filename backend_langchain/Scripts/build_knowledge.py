import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.sitemap import SitemapLoader
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma


def _safe_name(url: str) -> str:
    name = re.sub(r"^https?://", "", url)
    name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_-]", "_", name)
    return name[:180] or "doc"


def build_python_knowledge(
    sitemap_url: str,
    docs_dir: Path,
    chroma_dir: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
):
    print(f"[1/4] 加载站点地图: {sitemap_url}")
    loader = SitemapLoader(web_path=sitemap_url)
    raw_docs = loader.load()

    if not raw_docs:
        raise RuntimeError("未抓取到文档，请检查 sitemap_url 或网络连接")

    print(f"抓取完成，共 {len(raw_docs)} 篇文档")

    docs_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    print("[2/4] 保存原始文档到本地 docs 目录")
    for index, doc in enumerate(raw_docs, start=1):
        source_url = doc.metadata.get("source", f"doc_{index}")
        file_name = f"{index:05d}_{_safe_name(source_url)}.md"
        file_path = docs_dir / file_name

        content = (
            f"# Source\n{source_url}\n\n"
            f"# Metadata\n{doc.metadata}\n\n"
            f"# Content\n{doc.page_content}"
        )
        file_path.write_text(content, encoding="utf-8")

    print("[3/4] 文本切分")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"切分完成，共 {len(chunks)} 个文本块")

    print("[4/4] 向量化并写入 Chroma")
    embeddings = DashScopeEmbeddings(
        model=os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v2"),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
    )

    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(chroma_dir),
    )
    vector_db.persist()

    print("知识库构建完成")
    print(f"原始文档目录: {docs_dir}")
    print(f"向量库目录: {chroma_dir}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="构建 Python 官方文档 RAG 知识库")
    parser.add_argument(
        "--sitemap-url",
        default="https://python.langchain.com/sitemap.xml",
        help="站点地图地址",
    )
    parser.add_argument(
        "--docs-dir",
        default="Langchain_knowledge/docs",
        help="原始文档输出目录（相对 backend_langchain）",
    )
    parser.add_argument(
        "--chroma-dir",
        default="Langchain_knowledge/chroma_db",
        help="Chroma 持久化目录（相对 backend_langchain）",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=150)

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    docs_dir = (base_dir / args.docs_dir).resolve()
    chroma_dir = (base_dir / args.chroma_dir).resolve()

    build_python_knowledge(
        sitemap_url=args.sitemap_url,
        docs_dir=docs_dir,
        chroma_dir=chroma_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )


if __name__ == "__main__":
    main()
