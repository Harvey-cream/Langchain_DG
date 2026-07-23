"""诊断：用户上传文档为何对话检索不到。

在 backend_langchain 下运行：
  python Scripts/diagnose_user_rag.py
  python Scripts/diagnose_user_rag.py --user-id 6
  python Scripts/diagnose_user_rag.py --query "帮我找一下实习日志"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
for p in (_ROOT, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv

load_dotenv(_ROOT.parent / ".env")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def _section(title: str) -> None:
    print(f"\n== {title} ==")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


async def _resolve_user_id(cli_uid: int | None) -> int | None:
    if cli_uid is not None:
        return cli_uid
    try:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import AgentDocument

        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(AgentDocument.user_id)
                    .where(AgentDocument.status == "ready")
                    .order_by(AgentDocument.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if row is not None:
                return int(row)
    except Exception as e:  # noqa: BLE001
        _warn(f"从 Postgres 推断 user_id 失败: {e}")
    return None


async def _list_ready_docs(user_id: int | None) -> list[dict]:
    try:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import AgentDocument

        async with SessionLocal() as db:
            q = select(AgentDocument).where(AgentDocument.status == "ready")
            if user_id is not None:
                q = q.where(AgentDocument.user_id == user_id)
            q = q.order_by(AgentDocument.id.desc()).limit(10)
            rows = (await db.execute(q)).scalars().all()
            return [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "filename": r.filename,
                    "chunks": r.chunk_count,
                    "status": r.status,
                }
                for r in rows
            ]
    except Exception as e:  # noqa: BLE001
        _warn(f"读取 agent_documents 失败: {e}")
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="诊断 user_knowledge 检索失败原因")
    parser.add_argument("--user-id", type=int, default=None, help="pgvector 过滤用的 user_id")
    parser.add_argument(
        "--query",
        default="帮我找一下实习日志，内容是什么",
        help="测试问句",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    from config.config import CORPUS_USER
    from common.rag import (
        get_store,
        retrieve_context,
        search_hits,
    )

    _section("1) 配置")
    print(f"  corpus={CORPUS_USER}")
    print("  store=pgvector rag_embeddings")
    print("  distance threshold: removed (粗召回后由精排把关)")

    user_id = asyncio.run(_resolve_user_id(args.user_id))
    if user_id is None:
        _fail("未能确定 user_id，请传 --user-id")
        return 1
    _ok(f"user_id={user_id}")

    _section("2) Postgres 已入库文档")
    docs = asyncio.run(_list_ready_docs(user_id))
    if not docs:
        _warn("没有 status=ready 的 agent_documents（或读库失败）")
    for d in docs:
        print(
            f"  id={d['id']} user_id={d['user_id']} "
            f"file={d['filename']!r} chunks={d['chunks']} status={d['status']}"
        )

    _section("3) pgvector user corpus 概况")
    store = get_store()
    try:
        n = store.count(corpus=CORPUS_USER, user_id=user_id)
        n_all = store.count(corpus=CORPUS_USER)
        _ok(f"user_id={user_id} 向量条数={n}（corpus=user 合计 {n_all}）")
        if n == 0:
            _warn(f"库里没有 user_id={user_id} 的向量；检索会命中 0 条")
        sources = store.list_source_paths(corpus=CORPUS_USER, user_id=user_id)
        if sources:
            print(f"  source_path 样例: {sorted(sources)[:8]}")
    except Exception as e:  # noqa: BLE001
        _fail(f"读取 pgvector 失败: {e}")
        return 1

    query = (args.query or "").strip()
    _section(f"4) 原始相似度（带 user_id） query={query!r}")
    try:
        pairs = store.similarity_search_with_score(
            query,
            k=args.top_k,
            corpus=CORPUS_USER,
            user_id=user_id,
        )
        if not pairs:
            _warn("带 user_id：0 条（该用户无向量或问句不匹配）")
            pairs_all = store.similarity_search_with_score(
                query, k=args.top_k, corpus=CORPUS_USER
            )
            print(f"  不加 user_id 过滤 top{args.top_k}:")
            for doc, score in pairs_all:
                meta = doc.metadata or {}
                print(
                    f"    dist={float(score):.4f} user_id={meta.get('user_id')!r} "
                    f"source={meta.get('source_path')!r} "
                    f"text={(doc.page_content or '')[:60]!r}"
                )
        else:
            for doc, score in pairs:
                meta = doc.metadata or {}
                print(
                    f"  dist={float(score):.4f} "
                    f"source={meta.get('source_path')!r} "
                    f"text={(doc.page_content or '').replace(chr(10), ' ')[:70]!r}"
                )
    except Exception as e:  # noqa: BLE001
        _fail(f"similarity_search_with_score 失败: {e}")
        return 1

    _section("5) search_hits（生产同路径：user_id 过滤，无距离阈值）")
    hits = search_hits(
        query, corpus=CORPUS_USER, top_k=args.top_k, user_id=user_id
    )
    if not hits:
        _fail("search_hits 返回 0（门控之后若走到这里仍会「检索不到」）")
    else:
        _ok(f"search_hits={len(hits)}")
        for doc, dist in hits:
            meta = doc.metadata or {}
            print(
                f"  dist={dist:.4f} source={meta.get('source_path')!r} "
                f"text={(doc.page_content or '').replace(chr(10), ' ')[:70]!r}"
            )

    _section("6) RAG 门控 decide_rag_gate")
    try:
        from common.rag_gate import decide_rag_gate

        need = asyncio.run(
            decide_rag_gate(query, mode="main", skill_name="knowledge_qa")
        )
        if need:
            _ok(f"need_rag={need}（会继续检索）")
        else:
            _fail(
                f"need_rag={need}（对话链路会跳过检索；这常是「库有文档但回答说找不到」的主因）"
            )
    except Exception as e:  # noqa: BLE001
        _fail(f"门控调用失败（主线 fallback=False，等同不检索）: {e}")

    _section("7) retrieve_context（改写+召回+精排，与对话一致）")
    try:
        ctx = retrieve_context([query], corpus=CORPUS_USER, user_id=user_id)
        preview = (ctx or "").replace("\n", "\\n")[:400]
        if "未检索到" in (ctx or "") or "检索关键词为空" in (ctx or ""):
            _fail(f"retrieve_context 无有效命中: {preview}")
        else:
            _ok(f"retrieve_context 有内容 len={len(ctx or '')}")
            print(f"  preview: {preview}")
    except Exception as e:  # noqa: BLE001
        _fail(f"retrieve_context 异常: {e}")

    _section("结论提示")
    print(
        "  - 若第6步 need_rag=False：修门控（knowledge_qa 强制检索）\n"
        "  - 若第4步带 user_id 为0、不带过滤有结果：user_id 元数据/登录用户不一致\n"
        "  - 若第3步向量条数=0：入库未写入 rag_embeddings\n"
        "  - 粗召回不再做距离阈值；相关性由 rerank 把关"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
