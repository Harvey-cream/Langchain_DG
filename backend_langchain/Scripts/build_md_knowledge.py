"""
将 Markdown 入库到 Chroma（本地 HuggingFace embedding）。

默认：四套文档目录 → 四个独立 persist 目录（同 collection 名，靠路径隔离）。
自定义：--docs-dirs + --chroma-dir 合并进一个库。

下载 embedding 模型：默认通过 common.extend 设置 HF_ENDPOINT=https://hf-mirror.com（国内镜像）。
已在环境或 .env 中配置 HF_ENDPOINT 时不会被覆盖；需要直连官方可加参数 --no-hf-mirror。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# 直接运行本脚本时保证能 import backend_langchain 下的 common
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from common.extend import apply_hf_mirror_default
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG_RE = re.compile(r"<img\s+[^>]*>", flags=re.IGNORECASE)
_CHROMA_PAGE = 5000

# (key, docs 相对 backend_langchain, chroma 子目录相对 Langchain_knowledge/chroma_db)
DEFAULT_BASES: tuple[tuple[str, str, str], ...] = (
    ("ai_programming", "Langchain_knowledge/docs/AI编程工具与实战", "AI_programming"),
    ("openclaw", "Langchain_knowledge/docs/OpenClaw 保姆级教程", "Openclaw"),
    ("vibecoding", "Langchain_knowledge/docs/Vibe Coding 零基础教程", "Vibecoding"),
    ("learn_programing", "Langchain_knowledge/docs/编程学习路线与面试", "Learn_programing"),
)


def _strip_images(text: str, *, do_strip: bool) -> str:
    if not do_strip:
        return text
    text = _MD_IMAGE_RE.sub("", text)
    return _HTML_IMG_RE.sub("", text)


def _meta_for_file(rel_path: str, *, knowledge_base: str) -> dict:
    parts = rel_path.split("/")
    lang, top = "zh", parts[0] if parts else ""
    if len(parts) >= 3 and parts[0] == "translations":
        lang, top = parts[1], parts[2]
    return {"lang": lang, "top_section": top, "knowledge_base": knowledge_base}


def _source_key(file_path: Path, docs_roots: list[Path]) -> str | None:
    root = next((d for d in docs_roots if file_path.is_relative_to(d)), None)
    if not root:
        return None
    return f"{root.name}/{file_path.relative_to(root).as_posix()}"


def _chunk_ids(chunks: list[Document]) -> list[str]:
    ids: list[str] = []
    n: dict[str, int] = {}
    for ch in chunks:
        sp = ch.metadata.get("source_path", "unknown")
        i = n.get(sp, 0)
        ch.metadata["chunk_index"] = i
        ids.append(f"{sp}::chunk-{i}")
        n[sp] = i + 1
    return ids


def _existing_sources(chroma: Chroma) -> set[str]:
    out: set[str] = set()
    offset = 0
    while True:
        batch = chroma.get(include=["metadatas"], limit=_CHROMA_PAGE, offset=offset)
        metas = batch.get("metadatas") or []
        if not metas:
            break
        for m in metas:
            if m and (sp := m.get("source_path")):
                out.add(str(sp))
        if len(metas) < _CHROMA_PAGE:
            break
        offset += _CHROMA_PAGE
    return out


def _resolve_embedding_model(arg: str) -> str:
    raw = arg.strip()
    if not raw:
        raise ValueError("--embedding-model 不能为空")
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if p.is_dir():
        return str(p.resolve())
    if p.is_file():
        raise ValueError(f"--embedding-model 需要目录，不是文件: {raw!r}")
    looks_local = "\\" in raw or (len(raw) >= 2 and raw[1] == ":") or raw.startswith((".", "/", "\\"))
    if looks_local:
        raise FileNotFoundError(
            f"本地模型路径不存在: {raw!r}；或改用 HuggingFace id（如 BAAI/bge-small-zh-v1.5）。"
        )
    return raw


def _embeddings(model_ref: str, *, hf_cache: str | None, local_only: bool) -> HuggingFaceEmbeddings:
    mkw: dict = {"device": "cpu"}
    if local_only:
        mkw["local_files_only"] = True
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return HuggingFaceEmbeddings(
        model_name=model_ref,
        cache_folder=hf_cache,
        model_kwargs=mkw,
        encode_kwargs={"normalize_embeddings": True},
    )


def build_md_knowledge(
    docs_roots: list[Path],
    chroma_dir: Path,
    *,
    collection: str,
    model_arg: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    strip_images: bool = True,
    max_files: int | None = None,
    append: bool = False,
    hf_cache: str | None = None,
    local_only: bool = False,
    embeddings: HuggingFaceEmbeddings | None = None,
) -> None:
    """读取 docs_roots 下全部 .md → 切分 → 写入 chroma_dir。"""
    all_md: list[Path] = []
    for root in docs_roots:
        all_md.extend(sorted(root.rglob("*.md")))
    if not all_md:
        raise RuntimeError("未找到任何 .md 文件")

    if append:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        probe = Chroma(
            persist_directory=str(chroma_dir),
            embedding_function=None,
            collection_name=collection,
        )
        have = _existing_sources(probe)
        all_md = [p for p in all_md if (k := _source_key(p, docs_roots)) and k not in have]
        print(f"[增量] 待处理 {len(all_md)} 篇（已跳过库内已有）")

    if max_files is not None:
        all_md = all_md[:max_files]

    if not all_md:
        print("无需处理。")
        return

    print(f"[读取] {len(all_md)} 篇 md")
    raw_docs: list[Document] = []
    for i, path in enumerate(all_md, 1):
        root = next((d for d in docs_roots if path.is_relative_to(d)), None)
        if root is None:
            continue
        rel = path.relative_to(root).as_posix()
        sp = f"{root.name}/{rel}"
        md = _meta_for_file(rel, knowledge_base=root.name)
        md["source_path"] = sp
        text = _strip_images(path.read_text(encoding="utf-8"), do_strip=strip_images)
        raw_docs.append(
            Document(page_content=f"# Source: {sp}\n\n{text}".strip(), metadata=md)
        )
        if i % 50 == 0:
            print(f"  …{i}/{len(all_md)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(raw_docs)
    print(f"[切分] {len(chunks)} 块")

    model_ref = _resolve_embedding_model(model_arg)
    emb = embeddings or _embeddings(model_ref, hf_cache=hf_cache, local_only=local_only)
    ids = _chunk_ids(chunks)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    if append:
        db = Chroma(
            persist_directory=str(chroma_dir),
            embedding_function=emb,
            collection_name=collection,
        )
        db.add_documents(chunks, ids=ids)
    else:
        db = Chroma.from_documents(
            documents=chunks,
            embedding=emb,
            ids=ids,
            collection_name=collection,
            persist_directory=str(chroma_dir),
        )
    db.persist()
    print(f"[完成] {chroma_dir} | collection={collection} | model={model_ref}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="Markdown → Chroma（默认四套分库）")
    p.add_argument("--docs-dirs", nargs="+", default=None, help="自定义多文档根目录（须配合 --chroma-dir）")
    p.add_argument("--chroma-dir", default=None, help="自定义单一 Chroma 目录（相对 backend_langchain）")
    p.add_argument("--only", nargs="+", choices=[t[0] for t in DEFAULT_BASES], help="只构建部分默认库")
    p.add_argument("--collection-name", default="md_knowledge")
    p.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    p.add_argument("--hf-cache-dir", default=None)
    p.add_argument("--local-only", action="store_true")
    p.add_argument(
        "--no-hf-mirror",
        action="store_true",
        help="不设置默认 HF 镜像（仍可使用环境变量 HF_ENDPOINT 自行指定）",
    )
    p.add_argument("--chunk-size", type=int, default=1000)
    p.add_argument("--chunk-overlap", type=int, default=150)
    p.add_argument("--no-strip-images", action="store_true")
    p.add_argument("--max-files", type=int, default=None)
    p.add_argument("--append", action="store_true")
    args = p.parse_args()
    if args.no_hf_mirror:
        os.environ.pop("HF_ENDPOINT", None)
    else:
        apply_hf_mirror_default()

    base = Path(__file__).resolve().parent.parent
    kw = dict(
        collection=args.collection_name,
        model_arg=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        strip_images=not args.no_strip_images,
        max_files=args.max_files,
        append=args.append,
        hf_cache=args.hf_cache_dir,
        local_only=args.local_only,
    )

    if args.docs_dirs is not None:
        if not args.chroma_dir:
            p.error("--docs-dirs 必须配合 --chroma-dir")
        build_md_knowledge(
            [(base / d).resolve() for d in args.docs_dirs],
            (base / args.chroma_dir).resolve(),
            **kw,
        )
        return

    # 默认：四套分库，embedding 只加载一次
    keys = set(args.only) if args.only else None
    specs = [t for t in DEFAULT_BASES if keys is None or t[0] in keys]
    if keys:
        bad = keys - {t[0] for t in DEFAULT_BASES}
        if bad:
            raise SystemExit(f"未知 --only: {bad}")
    if not specs:
        raise SystemExit("没有可构建的库（检查 --only）")

    model_ref = _resolve_embedding_model(args.embedding_model)
    shared = _embeddings(model_ref, hf_cache=args.hf_cache_dir, local_only=args.local_only)
    print(f"四套分库，embedding 一次加载: {model_ref}")

    chroma_parent = base / "Langchain_knowledge" / "chroma_db"
    for key, docs_rel, sub in specs:
        docs_path = (base / docs_rel).resolve()
        if not docs_path.is_dir():
            raise FileNotFoundError(f"文档目录不存在: {docs_path}")
        print(f"\n--- {key} ---")
        build_md_knowledge(
            [docs_path],
            chroma_parent / sub,
            embeddings=shared,
            **kw,
        )


if __name__ == "__main__":
    main()
