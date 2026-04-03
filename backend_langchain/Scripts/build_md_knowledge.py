import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG_RE = re.compile(r"<img\s+[^>]*>", flags=re.IGNORECASE)

_CHROMA_GET_PAGE = 5000


def _clean_markdown(text: str, *, strip_images: bool) -> str:
    """
    为了减少 embedding 噪声，可选剥离图片引用行。
    （不改动代码块/正文结构）
    """
    if not strip_images:
        return text
    text = _MD_IMAGE_RE.sub("", text)
    text = _HTML_IMG_RE.sub("", text)
    return text


def _infer_metadata(rel_path_posix: str) -> dict:
    parts = rel_path_posix.split("/")
    lang = "zh"
    top_section = parts[0] if parts else ""

    if len(parts) >= 3 and parts[0] == "translations":
        lang = parts[1]
        top_section = parts[2]

    return {
        "source_path": rel_path_posix,
        "lang": lang,
        "top_section": top_section,
    }


def _source_path_for_md(file_path: Path, docs_dirs: list[Path]) -> str | None:
    parent_dir = next((d for d in docs_dirs if file_path.is_relative_to(d)), None)
    if not parent_dir:
        return None
    rel_path = file_path.relative_to(parent_dir).as_posix()
    return f"{parent_dir.name}/{rel_path}"


def _assign_per_source_chunk_ids(chunks: list[Document]) -> list[str]:
    ids: list[str] = []
    next_i: dict[str, int] = {}
    for chunk in chunks:
        source_path = chunk.metadata.get("source_path", "unknown")
        i = next_i.get(source_path, 0)
        chunk.metadata["chunk_index"] = i
        ids.append(f"{source_path}::chunk-{i}")
        next_i[source_path] = i + 1
    return ids


def _existing_source_paths(vector_db: Chroma) -> set[str]:
    paths: set[str] = set()
    offset = 0
    while True:
        batch = vector_db.get(
            include=["metadatas"],
            limit=_CHROMA_GET_PAGE,
            offset=offset,
        )
        metas = batch.get("metadatas") or []
        if not metas:
            break
        for m in metas:
            if m and (sp := m.get("source_path")):
                paths.add(str(sp))
        if len(metas) < _CHROMA_GET_PAGE:
            break
        offset += _CHROMA_GET_PAGE
    return paths


def _resolve_model_ref(model_arg: str) -> str:
    """
    --embedding-model 可为 HuggingFace repo id（如 BAAI/bge-small-zh-v1.5），
    或本机已下载的模型目录（路径须存在）。
    """
    raw = model_arg.strip()
    if not raw:
        raise ValueError("--embedding-model 不能为空")
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if p.exists() and p.is_dir():
        return str(p.resolve())
    if p.exists() and p.is_file():
        raise ValueError(f"--embedding-model 需要模型目录，不是单个文件: {raw!r}")
    # 明显是本地路径意图（含反斜杠、盘符、相对路径前缀），但目录不存在
    path_intent = (
        "\\" in raw
        or (len(raw) >= 2 and raw[1] == ":")
        or raw.startswith((".", "/", "\\"))
    )
    if path_intent:
        raise FileNotFoundError(
            f"本地模型路径不存在或不是目录: {raw!r}\n"
            "请填写本机真实路径，或使用 HuggingFace id（如 BAAI/bge-small-zh-v1.5）。"
        )
    return raw


def _make_embeddings(
    *,
    model_ref: str,
    hf_cache_dir: str | None,
    local_only: bool,
) -> HuggingFaceEmbeddings:
    model_kwargs: dict = {"device": "cpu"}
    if local_only:
        model_kwargs["local_files_only"] = True
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return HuggingFaceEmbeddings(
        model_name=model_ref,
        cache_folder=hf_cache_dir,
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": True},
    )


def build_md_knowledge(
    docs_dirs: list[Path],
    chroma_dir: Path,
    *,
    collection_name: str,
    embedding_model_name: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    strip_images: bool = True,
    max_files: int | None = None,
    append: bool = False,
    hf_cache_dir: str | None = None,
    local_only: bool = False,
):
    all_md: list[Path] = []
    for docs_dir in docs_dirs:
        all_md.extend(sorted(docs_dir.rglob("*.md")))

    if not all_md:
        raise RuntimeError("在指定 docs 目录下未找到任何 .md 文件")

    md_files = all_md
    if append:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        vector_probe = Chroma(
            persist_directory=str(chroma_dir),
            embedding_function=None,
            collection_name=collection_name,
        )
        existing = _existing_source_paths(vector_probe)
        md_files = [
            p
            for p in all_md
            if (sp := _source_path_for_md(p, docs_dirs)) is not None and sp not in existing
        ]
        skipped = len(all_md) - len(md_files)
        print(
            f"[0/4] 增量模式：库中已有 {len(existing)} 个文档路径，跳过已入库 {skipped} 篇，待处理 {len(md_files)} 篇"
        )
        if max_files is not None:
            md_files = md_files[:max_files]
    else:
        if max_files is not None:
            md_files = md_files[:max_files]

    if not md_files:
        print("没有需要入库的 .md 文件（可能已全部在库中或 max-files 为 0）")
        return

    print(f"[1/4] 发现 .md 文件: {len(md_files)} 篇")

    raw_docs: list[Document] = []
    for i, file_path in enumerate(md_files, start=1):
        parent_dir = next((d for d in docs_dirs if file_path.is_relative_to(d)), None)
        if not parent_dir:
            continue
        rel_path = file_path.relative_to(parent_dir).as_posix()
        source_path = f"{parent_dir.name}/{rel_path}"
        metadata = _infer_metadata(rel_path)
        metadata["source_path"] = source_path

        text = file_path.read_text(encoding="utf-8")
        text = _clean_markdown(text, strip_images=strip_images)

        page_content = f"# Source: {source_path}\n\n{text}".strip()
        raw_docs.append(Document(page_content=page_content, metadata=metadata))

        if i % 50 == 0:
            print(f"  已读取 {i}/{len(md_files)}")

    print("[2/4] 文本切分")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(raw_docs)
    print(f"切分完成，共 {len(chunks)} 个文本块")

    print("[3/4] 使用本地向量模型并写入 Chroma")
    model_ref = _resolve_model_ref(embedding_model_name)
    embeddings = _make_embeddings(
        model_ref=model_ref,
        hf_cache_dir=hf_cache_dir,
        local_only=local_only,
    )
    ids = _assign_per_source_chunk_ids(chunks)

    chroma_dir.mkdir(parents=True, exist_ok=True)

    if append:
        vector_db = Chroma(
            persist_directory=str(chroma_dir),
            embedding_function=embeddings,
            collection_name=collection_name,
        )
        vector_db.add_documents(chunks, ids=ids)
    else:
        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            ids=ids,
            collection_name=collection_name,
            persist_directory=str(chroma_dir),
        )
    vector_db.persist()

    print("知识库构建完成")
    print(f"原始文档目录: {[str(d) for d in docs_dirs]}")
    print(f"向量库目录: {chroma_dir}")
    print(f"collection_name: {collection_name}")
    print(f"embedding_model: {model_ref}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="将本地 Markdown 知识库入库到 Chroma（本地 embedding）")
    parser.add_argument(
        "--docs-dirs",
        nargs="+",
        default=[
            "Langchain_knowledge/docs/OpenClaw 保姆级教程",
            "Langchain_knowledge/docs/Vibe Coding 零基础教程",
        ],
        help="Markdown 知识库目录列表（相对 backend_langchain）",
    )
    parser.add_argument(
        "--chroma-dir",
        default="Langchain_knowledge/chroma_db",
        help="Chroma 持久化目录（相对 backend_langchain）",
    )
    parser.add_argument(
        "--collection-name",
        default="vibe_openclaw_md",
        help="Chroma collection 名称",
    )
    parser.add_argument(
        "--embedding-model",
        default="BAAI/bge-small-zh-v1.5",
        help="HuggingFace 模型 id，或本机已下载的模型目录（绝对/相对路径均可）",
    )
    parser.add_argument(
        "--hf-cache-dir",
        default=None,
        help="SentenceTransformers/HuggingFace 缓存目录，减轻重复下载",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="仅使用本地缓存/目录，不访问 HuggingFace（需模型已在 cache 或 --embedding-model 为本地目录）",
    )
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument(
        "--no-strip-images",
        action="store_true",
        help="不剥离图片引用（会增加噪声与 token）",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="非 append：只处理排序后前 N 个 md；append：在「未入库」列表上再截断 N 个",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="增量入库：跳过 Chroma 中已有 source_path 的文档",
    )

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    docs_dirs = [(base_dir / d).resolve() for d in args.docs_dirs]
    chroma_dir = (base_dir / args.chroma_dir).resolve()

    build_md_knowledge(
        docs_dirs=docs_dirs,
        chroma_dir=chroma_dir,
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        strip_images=not args.no_strip_images,
        max_files=args.max_files,
        append=args.append,
        hf_cache_dir=args.hf_cache_dir,
        local_only=args.local_only,
    )


if __name__ == "__main__":
    main()
