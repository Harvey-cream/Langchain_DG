"""
RAG 全链路评测：精排 API 连通性 + 多问句召回率。

用法（backend_langchain 目录）：
  python Scripts/test_rag_pipeline.py check-rerank
  python Scripts/test_rag_pipeline.py recall -y
  python Scripts/test_rag_pipeline.py recall --full -y   # 含问句改写（额外 LLM）
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT.parent / ".env")

from langchain_core.documents import Document

from infrastructure.rag.rag import _merge_hits, get_store, search_hits
from infrastructure.rag.rerank import _dashscope_rerank, rerank_documents
from config.config import (
    CORPUS_AGENT,
    RECALL_K,
    RERANK_TOP_K,
    dashscope_api_key,
    dashscope_rerank_model,
)

# query → 期望 top 结果正文/来源应含其一（粗算 keyword recall@k）
RECALL_CASES: list[dict[str, object]] = [
    # --- ai_programming ---
    {"group": "ai_programming", "query": "零代码平台有哪些代表工具", "keywords": ["零代码", "Bolt", "Lovable"]},
    {"group": "ai_programming", "query": "Cursor 属于哪类 AI 编程工具", "keywords": ["Cursor", "代码编辑器"]},
    {"group": "ai_programming", "query": "Claude Code 是什么类型的工具", "keywords": ["Claude Code", "命令行"]},
    {"group": "ai_programming", "query": "AI 智能体平台有哪些", "keywords": ["智能体", "Agent"]},
    {"group": "ai_programming", "query": "Dify 是什么平台", "keywords": ["Dify"]},
    {"group": "ai_programming", "query": "GitHub Copilot 怎么用", "keywords": ["Copilot", "VSCode"]},
    {"group": "ai_programming", "query": "为什么要了解 AI 编程工具", "keywords": ["效率", "工具"]},
    {"group": "ai_programming", "query": "AI 模型选择要注意什么", "keywords": ["模型", "选择"]},
    {"group": "ai_programming", "query": "Bolt.new 有什么特点", "keywords": ["Bolt"]},
    {"group": "ai_programming", "query": "Manus 智能体平台怎么样", "keywords": ["Manus"]},
    {"group": "ai_programming", "query": "Flowith 是什么 AI 工具", "keywords": ["Flowith"]},
    {"group": "ai_programming", "query": "Gemini CLI 有什么坑", "keywords": ["Gemini CLI"]},
    {"group": "ai_programming", "query": "TRAE SOLO 和 Cursor 有什么区别", "keywords": ["TRAE", "SOLO"]},
    {"group": "ai_programming", "query": "OpenSpec 规范开发框架是什么", "keywords": ["OpenSpec"]},
    {"group": "ai_programming", "query": "AI IDE 插件有哪些推荐", "keywords": ["IDE", "插件"]},
    {"group": "ai_programming", "query": "AI 辅助工具集包含什么", "keywords": ["辅助工具"]},
    {"group": "ai_programming", "query": "Remotion 能做什么", "keywords": ["Remotion"]},
    {"group": "ai_programming", "query": "百度秒哒零代码平台特点", "keywords": ["秒哒", "零代码"]},
    {"group": "ai_programming", "query": "v0 是什么 AI 工具", "keywords": ["v0"]},
    {"group": "ai_programming", "query": "AI 编程工具有哪几大类", "keywords": ["零代码", "代码编辑器", "命令行"]},
    # --- openclaw ---
    {"group": "openclaw", "query": "OpenClaw 是什么", "keywords": ["OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 怎么本地安装", "keywords": ["安装", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw Skills 技能系统是什么", "keywords": ["Skills", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 多 Agent 协作怎么做", "keywords": ["多 Agent", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 怎么接入 QQ 和飞书", "keywords": ["QQ", "飞书"]},
    {"group": "openclaw", "query": "OpenClaw 云端部署怎么做", "keywords": ["部署", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 安全指南要注意什么", "keywords": ["安全", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 记忆管理怎么控制成本", "keywords": ["记忆", "成本"]},
    {"group": "openclaw", "query": "OpenClaw 定时任务怎么用", "keywords": ["定时", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 模型怎么切换", "keywords": ["模型", "OpenClaw"]},
    {"group": "openclaw", "query": "OpenClaw 一键安装脚本在哪", "keywords": ["安装", "脚本"]},
    {"group": "openclaw", "query": "OpenClaw 工具管理和多媒体能力", "keywords": ["工具", "多媒体"]},
    # --- vibe_coding ---
    {"group": "vibe_coding", "query": "Vibe Coding 五大核心心法", "keywords": ["心法", "Vibe Coding"]},
    {"group": "vibe_coding", "query": "Vibe Coding 上下文管理技巧", "keywords": ["上下文"]},
    {"group": "vibe_coding", "query": "如何处理 AI 幻觉和死循环", "keywords": ["幻觉", "死循环"]},
    {"group": "vibe_coding", "query": "Vibe Coding 项目开发流程", "keywords": ["流程", "Vibe Coding"]},
    {"group": "vibe_coding", "query": "Vibe Coding 成本控制技巧", "keywords": ["成本"]},
    {"group": "vibe_coding", "query": "Vibe Coding 对话工程技巧", "keywords": ["对话"]},
    {"group": "vibe_coding", "query": "Vibe Coding 代码质量怎么保障", "keywords": ["代码质量"]},
    {"group": "vibe_coding", "query": "Vibe Coding 性能优化怎么做", "keywords": ["性能"]},
    {"group": "vibe_coding", "query": "Vibe Coding 全栈应用怎么开发", "keywords": ["全栈"]},
    {"group": "vibe_coding", "query": "Vibe Coding 项目怎么部署上线", "keywords": ["部署", "上线"]},
    {"group": "vibe_coding", "query": "Vibe Coding 效率提升有哪些技巧", "keywords": ["效率"]},
    {"group": "vibe_coding", "query": "Vibe Coding 代码重构技巧", "keywords": ["重构"]},
    {"group": "vibe_coding", "query": "什么是 Vibe Coding", "keywords": ["Vibe Coding"]},
    # --- learn_programing ---
    {"group": "learn_programing", "query": "MCP 是什么", "keywords": ["MCP"]},
    {"group": "learn_programing", "query": "程序员面试刷题有什么建议", "keywords": ["面试", "刷题"]},
    {"group": "learn_programing", "query": "AI 应用开发面试题有哪些方向", "keywords": ["AI 应用", "面试"]},
    {"group": "learn_programing", "query": "编程学习路线怎么规划", "keywords": ["学习", "路线"]},
    {"group": "learn_programing", "query": "程序员简历怎么写", "keywords": ["简历"]},
    {"group": "learn_programing", "query": "程序员成长有哪些方法", "keywords": ["成长"]},
    {"group": "learn_programing", "query": "MCP 服务怎么开发", "keywords": ["MCP", "开发"]},
    {"group": "learn_programing", "query": "AI 时代程序员必须做什么", "keywords": ["程序员", "AI"]},
    {"group": "learn_programing", "query": "编程资源大全有哪些", "keywords": ["资源"]},
    {"group": "learn_programing", "query": "团队研发规范有哪些要点", "keywords": ["研发规范", "规范"]},
    # --- 指代/口语（--full 时测改写）---
    {"group": "coreference", "query": "它怎么部署到云端", "keywords": ["部署", "OpenClaw"], "recent": "用户：OpenClaw 是什么\n助手：OpenClaw 是开源 AI 助手框架。"},
    {"group": "coreference", "query": "这个和 Cursor 有什么区别", "keywords": ["区别", "Cursor"], "recent": "用户：Bolt 是什么\n助手：Bolt 是零代码 AI 编程平台。"},
    {"group": "coreference", "query": "那它的 Skills 怎么用", "keywords": ["Skills", "OpenClaw"], "recent": "用户：OpenClaw 是什么\n助手：OpenClaw 支持技能扩展。"},
    {"group": "coreference", "query": "刚才说的那个怎么控制花费", "keywords": ["成本", "控制"], "recent": "用户：Vibe Coding 成本很高怎么办\n助手：可以通过选模型和控制上下文来省钱。"},
]


@dataclass
class StageMetrics:
    name: str
    hit_at_1: int = 0
    hit_at_3: int = 0
    hit_at_k: int = 0
    no_hits: int = 0
    total: int = 0

    def add(self, *, top_docs: list[Document], keywords: list[str], k: int) -> None:
        self.total += 1
        if not top_docs:
            self.no_hits += 1
            return
        texts = [_doc_text(d) for d in top_docs]
        hits = [_keyword_hit(t, keywords) for t in texts]
        if any(hits[:1]):
            self.hit_at_1 += 1
        if any(hits[:3]):
            self.hit_at_3 += 1
        if any(hits[:k]):
            self.hit_at_k += 1

    def report(self, k: int) -> str:
        if self.total == 0:
            return f"{self.name}: (无样本)"
        t = self.total
        return (
            f"{self.name}: "
            f"@1={self.hit_at_1}/{t} ({100*self.hit_at_1/t:.0f}%) | "
            f"@3={self.hit_at_3}/{t} ({100*self.hit_at_3/t:.0f}%) | "
            f"@{k}={self.hit_at_k}/{t} ({100*self.hit_at_k/t:.0f}%) | "
            f"无结果={self.no_hits}"
        )


def _group_of(case: dict[str, object]) -> str:
    return str(case.get("group") or "other")


def _console(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


def _doc_text(doc: Document) -> str:
    meta = doc.metadata or {}
    sp = str(meta.get("source_path") or "")
    return f"{sp}\n{doc.page_content or ''}"


def _keyword_hit(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _print_top(label: str, docs: list[Document], *, show: int = 3) -> None:
    print(f"  {label}:")
    if not docs:
        print("    (无命中)")
        return
    for i, doc in enumerate(docs[:show], start=1):
        meta = doc.metadata or {}
        sp = Path(str(meta.get("source_path") or "")).name
        body = (doc.page_content or "").strip()[:120].replace("\n", " ")
        print(_console(f"    #{i} [{sp}] {body}…"))


def cmd_check_rerank(_: argparse.Namespace) -> int:
    print("=== 精排 API 连通性 ===")
    key = dashscope_api_key()
    if not key:
        print("FAIL: 未配置 DASHSCOPE_API_KEY")
        return 1
    model = dashscope_rerank_model()
    print(f"model={model}")
    query = "什么是 OpenClaw"
    docs = [
        "OpenClaw 是一个开源 AI 助手框架，支持本地与云端部署。",
        "Vue 3 组合式 API 是前端框架特性。",
        "Java HashMap 底层是数组加链表或红黑树。",
    ]
    try:
        indices = _dashscope_rerank(query, docs, top_n=2)
        print(f"OK: rerank 返回 index={indices}")
        for rank, idx in enumerate(indices, start=1):
            print(_console(f"  #{rank} → {docs[idx][:60]}…"))
        if indices and indices[0] == 0:
            print("OK: 最相关文档排在首位（符合预期）")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


def _vector_top_k(questions: list[str], *, corpus: str, recall_k: int, top_k: int) -> list[Document]:
    batches = [search_hits(q, corpus=corpus, top_k=recall_k) for q in questions]
    merged = _merge_hits(batches)
    return [doc for doc, _ in merged[:top_k]]


def _pipeline_top_k(
    questions: list[str], *, corpus: str, recall_k: int, top_k: int
) -> list[Document]:
    batches = [search_hits(q, corpus=corpus, top_k=recall_k) for q in questions]
    merged = _merge_hits(batches)
    if not merged:
        return []
    return rerank_documents(questions[0], merged, top_k=top_k)


async def _resolve_questions(
    case: dict[str, object], *, use_rewrite: bool
) -> list[str]:
    query = str(case["query"])
    if not use_rewrite:
        return [query]
    from infrastructure.rag.retrieval_planner import plan_retrieval

    recent = str(case.get("recent") or "")
    plan = await plan_retrieval(
        query,
        mode="main",
        skill_name="knowledge_qa",
        recent_dialogue=recent,
    )
    if not plan.need_rag:
        return [query]
    return plan.search_questions or [query]


async def cmd_recall_async(args: argparse.Namespace) -> int:
    store = get_store()
    if store.count(corpus=CORPUS_AGENT) == 0:
        print("FAIL: 向量库为空，请先构建: python Scripts/build_rag_knowledge.py")
        return 1
    if not dashscope_api_key():
        print("WARN: 未配置 DASHSCOPE_API_KEY，嵌入/精排可能失败")

    corpus = CORPUS_AGENT
    recall_k = args.recall_k
    top_k = args.top_k
    cases = RECALL_CASES
    if args.limit:
        cases = cases[: args.limit]

    print("\n=== RAG 全链路召回评测 ===")
    print(
        f"corpus={corpus} | recall_k={recall_k} | rerank_top_k={top_k} | "
        f"cases={len(cases)} | rewrite={'on' if args.full else 'off'}"
    )

    if not args.yes:
        est = len(cases) * (3 if args.full else 2)
        ans = input(f"预计约 {est}+ 次 DashScope 调用，继续? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消")
            return 0

    m_vec = StageMetrics("向量粗排(top by distance)")
    m_pipe = StageMetrics("粗召回+精排(生产链路)")
    g_vec: dict[str, StageMetrics] = {}
    g_pipe: dict[str, StageMetrics] = {}
    failures: list[str] = []

    for i, case in enumerate(cases, start=1):
        query = str(case["query"])
        keywords = [str(k) for k in case.get("keywords", [])]
        group = _group_of(case)
        if not args.quiet:
            print(f"\n--- [{i}/{len(cases)}] [{group}] {query} ---")
            if keywords:
                print(f"  期望关键词: {keywords}")

        questions = await _resolve_questions(case, use_rewrite=args.full)
        if args.full and len(questions) != 1 and not args.quiet:
            print(f"  改写问句: {questions}")

        vec_docs = _vector_top_k(questions, corpus=corpus, recall_k=recall_k, top_k=top_k)
        pipe_docs = _pipeline_top_k(questions, corpus=corpus, recall_k=recall_k, top_k=top_k)

        if not args.quiet:
            _print_top("向量 top", vec_docs)
            _print_top("精排 top", pipe_docs)

        if keywords:
            m_vec.add(top_docs=vec_docs, keywords=keywords, k=top_k)
            m_pipe.add(top_docs=pipe_docs, keywords=keywords, k=top_k)
            if group not in g_vec:
                g_vec[group] = StageMetrics(f"{group}/向量")
                g_pipe[group] = StageMetrics(f"{group}/精排")
            g_vec[group].add(top_docs=vec_docs, keywords=keywords, k=top_k)
            g_pipe[group].add(top_docs=pipe_docs, keywords=keywords, k=top_k)
            v_hit = any(_keyword_hit(_doc_text(d), keywords) for d in vec_docs[:top_k])
            p_hit = any(_keyword_hit(_doc_text(d), keywords) for d in pipe_docs[:top_k])
            if not args.quiet:
                print(f"  关键词 @{top_k}: 向量={'Y' if v_hit else 'N'} | 精排={'Y' if p_hit else 'N'}")
            if not p_hit:
                failures.append(f"[{group}] {query} (精排未命中)")

    print("\n=== 汇总 ===")
    if m_vec.total:
        print(m_vec.report(top_k))
        print(m_pipe.report(top_k))
        delta = m_pipe.hit_at_k - m_vec.hit_at_k
        sign = "+" if delta >= 0 else ""
        print(f"精排相对向量 @{top_k}: {sign}{delta} 题 ({sign}{100*delta/m_vec.total:.0f}%)")
        print("\n--- 分组 ---")
        for group in sorted(g_vec):
            print(g_vec[group].report(top_k))
            print(g_pipe[group].report(top_k))
        if failures:
            print(f"\n--- 未命中 ({len(failures)}) ---")
            for line in failures:
                print(_console(f"  {line}"))
    else:
        print("（无带关键词标注的样本）")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    return asyncio.run(cmd_recall_async(args))


def main() -> None:
    p = argparse.ArgumentParser(description="RAG 精排 API + 全链路召回评测")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check-rerank", help="测试 DashScope qwen3-rerank API 是否可用")

    rec = sub.add_parser("recall", help="多问句粗召回 + 精排，统计 keyword recall")
    rec.add_argument("--recall-k", type=int, default=RECALL_K)
    rec.add_argument("--top-k", type=int, default=RERANK_TOP_K)
    rec.add_argument("--full", action="store_true", help="启用问句改写（额外 LLM）")
    rec.add_argument("--limit", type=int, default=None, help="只跑前 N 题")
    rec.add_argument("-q", "--quiet", action="store_true", help="只输出汇总与未命中")
    rec.add_argument("-y", "--yes", action="store_true", help="跳过确认")

    args = p.parse_args()
    if args.cmd == "check-rerank":
        raise SystemExit(cmd_check_rerank(args))
    raise SystemExit(cmd_recall(args))


if __name__ == "__main__":
    main()
