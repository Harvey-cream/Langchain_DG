"""
Agent 响应延迟诊断：分阶段计时，区分「模型慢」还是「Agent 某步慢」。

用法（backend_langchain 目录）：
  python Scripts/benchmark_agent_latency.py -y
  python Scripts/benchmark_agent_latency.py -y --limit 3
  python Scripts/benchmark_agent_latency.py -y --cases greeting,knowledge
  python Scripts/benchmark_agent_latency.py -y --warmup

阶段说明：
  skill_route        Skill 向量路由（本地/HF 嵌入）
  retrieval_plan     Retrieval Planner LLM（need_rag + 问句，原 gate+rewrite）
  rag_retrieve       向量召回 + DashScope 精排
  skill_recall       上述 Workflow 合计（≈ skill_recall 节点）
  llm_ttft           直连模型首 token（基线，无 Agent）
  agent_ttft         完整 Agent 首 token（含 Workflow + 模型）
  agent_total        完整 Agent 流结束
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT.parent / ".env")

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph_factory import close_checkpointer, init_checkpointer, stream_graph_chat_model_events
from app.services.extend import quick_agent_greeting_prompt
from agent.rag.rag import retrieve_context, search_hits
from agent.rag.retrieval_planner import plan_retrieval
from agent.rag.skill_router import AGENT_SKILLS, _pick_skill, prepare_turn_context, warmup_skill_phrase_cache
from config.config import CORPUS_AGENT, get_qwen_chat_model
from app.settings import llm_config
from agent.runtime.runtime_knowledge import get_stream_agent_executor, reset_knowledge_agent_cache

# id, 问句, 简述（便于读报告）
BENCH_CASES: list[dict[str, str]] = [
    {
        "id": "greeting",
        "query": "你好",
        "note": "寒暄，走 quick 短路或极短回复",
    },
    {
        "id": "knowledge",
        "query": "什么是 OpenClaw？用两三句话说明。",
        "note": "知识库问答，预期 RAG + 模型",
    },
    {
        "id": "knowledge2",
        "query": "Vibe Coding 五大核心心法是什么？",
        "note": "另一知识域，测检索链路",
    },
    {
        "id": "coding",
        "query": "Python 报错 TypeError: 'NoneType' object is not subscriptable，怎么排查？",
        "note": "代码排查，门控倾向不检索",
    },
    {
        "id": "compare",
        "query": "Cursor 和 Claude Code 有什么区别？",
        "note": "对比类，可能检索 + 较长生成",
    },
    {
        "id": "short",
        "query": "说一个字：好",
        "note": "极短生成，测模型/API 下限延迟",
    },
]


@dataclass
class StageTimes:
    """单题各阶段耗时（秒）；None 表示未执行。"""

    skill_route: float | None = None
    retrieval_plan: float | None = None
    rag_retrieve: float | None = None
    skill_recall: float | None = None
    llm_ttft: float | None = None
    agent_ttft: float | None = None
    agent_total: float | None = None
    skill_name: str = ""
    need_rag: bool | None = None
    rewrite_questions: list[str] = field(default_factory=list)
    delta_count: int = 0
    quick_path: bool = False
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill_route": self.skill_route,
            "retrieval_plan": self.retrieval_plan,
            "rag_retrieve": self.rag_retrieve,
            "skill_recall": self.skill_recall,
            "llm_ttft": self.llm_ttft,
            "agent_ttft": self.agent_ttft,
            "agent_total": self.agent_total,
            "skill_name": self.skill_name,
            "need_rag": self.need_rag,
            "rewrite_questions": self.rewrite_questions,
            "delta_count": self.delta_count,
            "quick_path": self.quick_path,
            "error": self.error,
        }


def _ms(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    return f"{seconds * 1000:.0f}ms"


def _console(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


async def _time_skill_route(query: str) -> tuple[float, str]:
    t0 = time.perf_counter()
    spec = _pick_skill(query, AGENT_SKILLS)
    return time.perf_counter() - t0, spec.name if spec else ""


async def _time_retrieval_plan(
    query: str, skill_name: str | None
) -> tuple[float, bool, list[str]]:
    t0 = time.perf_counter()
    plan = await plan_retrieval(
        query,
        mode="main",
        skill_name=skill_name,
        recent_dialogue="",
    )
    return time.perf_counter() - t0, bool(plan.need_rag), list(plan.search_questions or [])


def _time_rag_retrieve(questions: list[str]) -> float:
    t0 = time.perf_counter()
    retrieve_context(questions, corpus=CORPUS_AGENT)
    return time.perf_counter() - t0


async def _time_skill_recall(query: str) -> tuple[float, str, str]:
    t0 = time.perf_counter()
    spec, _, retrieved = await prepare_turn_context(query, mode="main", recent_dialogue="")
    elapsed = time.perf_counter() - t0
    skill = spec.name if spec else ""
    preview = (retrieved or "").strip()[:80].replace("\n", " ")
    return elapsed, skill, preview


async def _time_llm_ttft(query: str) -> float:
    llm = get_qwen_chat_model(temperature=0.45, streaming=True)
    msgs = [
        SystemMessage(content="你是助手。尽量简洁回答。"),
        HumanMessage(content=query),
    ]
    t0 = time.perf_counter()
    async for chunk in llm.astream(msgs):
        text = getattr(chunk, "content", None)
        if text:
            return time.perf_counter() - t0
    return time.perf_counter() - t0


async def _time_agent_stream(
    query: str,
    thread_id: str,
) -> tuple[float | None, float, int, list[str]]:
    """返回 (ttft, total, delta_count, status_texts)。"""
    agent = get_stream_agent_executor(temperature=0.45, enable_web_search=False)
    t0 = time.perf_counter()
    ttft: float | None = None
    deltas = 0
    statuses: list[str] = []

    async for evt in stream_graph_chat_model_events(
        agent,
        prompt_text=query,
        thread_id=thread_id,
    ):
        t = evt.get("type")
        if t == "status" and evt.get("text"):
            statuses.append(str(evt["text"]))
        elif t == "delta" and evt.get("text"):
            deltas += 1
            if ttft is None:
                ttft = time.perf_counter() - t0

    total = time.perf_counter() - t0
    return ttft, total, deltas, statuses


async def benchmark_one(case: dict[str, str], *, run_idx: int) -> StageTimes:
    query = case["query"]
    case_id = case["id"]
    out = StageTimes()
    thread_id = f"bench:{case_id}:{run_idx}:{int(time.time() * 1000)}"

    if quick_agent_greeting_prompt(query):
        out.quick_path = True

    try:
        dt, skill = await _time_skill_route(query)
        out.skill_route = dt
        out.skill_name = skill

        dt, need, questions = await _time_retrieval_plan(query, skill or None)
        out.retrieval_plan = dt
        out.need_rag = need
        out.rewrite_questions = questions
        if need:
            out.rag_retrieve = _time_rag_retrieve(questions or [query])

        dt, skill2, _ = await _time_skill_recall(query)
        out.skill_recall = dt
        if skill2 and not out.skill_name:
            out.skill_name = skill2

        out.llm_ttft = await _time_llm_ttft(query)
    except Exception as e:  # noqa: BLE001
        out.error = f"workflow/llm: {type(e).__name__}: {e}"
        return out

    try:
        ttft, total, deltas, statuses = await _time_agent_stream(query, thread_id)
        out.agent_ttft = ttft
        out.agent_total = total
        out.delta_count = deltas
        if statuses and out.need_rag is None:
            out.need_rag = any("搜索" in s for s in statuses)
    except Exception as e:  # noqa: BLE001
        out.error = f"agent: {type(e).__name__}: {e}"

    return out


def _print_case_detail(case: dict[str, str], st: StageTimes) -> None:
    q = case["query"]
    print(f"\n--- [{case['id']}] {case['note']} ---")
    print(_console(f"  问句: {q}"))
    if st.quick_path:
        print("  路径: quick 短路（stream.py 不经完整图）")
    if st.skill_name or st.need_rag is not None:
        print(f"  skill={st.skill_name or '—'} | need_rag={st.need_rag}")
    if st.rewrite_questions:
        print(_console(f"  改写问句: {st.rewrite_questions}"))
    if any(
        v is not None
        for v in (st.skill_route, st.retrieval_plan, st.rag_retrieve, st.skill_recall)
    ):
        print(
            "  Workflow: "
            f"route={_ms(st.skill_route)} | "
            f"planner={_ms(st.retrieval_plan)} | "
            f"retrieve={_ms(st.rag_retrieve)} | "
            f"合计 skill_recall={_ms(st.skill_recall)}"
        )
    if st.llm_ttft is not None or st.agent_ttft is not None:
        print(
            "  模型/Agent: "
            f"llm_ttft={_ms(st.llm_ttft)} | "
            f"agent_ttft={_ms(st.agent_ttft)} | "
            f"agent_total={_ms(st.agent_total)} | "
            f"deltas={st.delta_count}"
        )
    if st.agent_ttft is not None and st.skill_recall is not None and st.llm_ttft is not None:
        overhead = st.agent_ttft - st.llm_ttft
        print(
            f"  粗算: Workflow≈{_ms(st.skill_recall)} | "
            f"Agent首token比直连模型多≈{_ms(max(0.0, overhead))}"
        )
    if st.error:
        print(f"  ERROR: {st.error}")
    if not st.error or st.llm_ttft is not None:
        _print_bottleneck_hint(st)


def _print_bottleneck_hint(st: StageTimes) -> None:
    if st.error:
        return
    parts: list[tuple[str, float]] = []
    for name, val in (
        ("skill_route", st.skill_route),
        ("retrieval_plan", st.retrieval_plan),
        ("rag_retrieve", st.rag_retrieve),
        ("llm_ttft(基线)", st.llm_ttft),
    ):
        if val is not None and val > 0:
            parts.append((name, val))
    if not parts:
        return
    parts.sort(key=lambda x: x[1], reverse=True)
    top_name, top_val = parts[0]
    hints: list[str] = [f"Workflow 内最慢: {top_name} ({_ms(top_val)})"]

    if st.llm_ttft is not None and st.llm_ttft >= 2.0:
        hints.append("直连模型首 token ≥2s → 优先查 LLM API/模型/网络")
    if st.retrieval_plan and st.retrieval_plan >= 1.0:
        hints.append("Retrieval Planner LLM 偏慢 → 可规则短路 need_rag 或关 QUERY_REWRITE_ENABLED")
    if st.rag_retrieve and st.rag_retrieve >= 1.5:
        hints.append("检索+精排偏慢 → 查 pgvector/嵌入 API/精排 API")
    if st.skill_route and st.skill_route >= 0.5:
        hints.append("Skill 路由嵌入偏慢 → 确认已 warmup_skill_phrase_cache")
    if (
        st.agent_ttft is not None
        and st.llm_ttft is not None
        and st.agent_ttft - st.llm_ttft > 1.5
        and (st.skill_recall or 0) < st.agent_ttft - st.llm_ttft - 0.5
    ):
        hints.append("Agent 额外开销大 → 查 checkpoint/上下文长度/工具调用")

    print("  诊断: " + "；".join(hints))


def _avg(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _print_summary(rows: list[tuple[dict[str, str], StageTimes]]) -> None:
    print("\n" + "=" * 72)
    print("汇总（各阶段平均耗时）")
    print("=" * 72)
    headers = [
        "id",
        "route",
        "gate",
        "rewrite",
        "retrieve",
        "recall",
        "llm_ttft",
        "agent_ttft",
        "agent_total",
    ]
    print(
        f"{'id':<12} {'route':>8} {'planner':>8} {'retrieve':>9} "
        f"{'recall':>8} {'llm_ttft':>9} {'ag_ttft':>9} {'ag_total':>10}"
    )
    print("-" * 72)
    for case, st in rows:
        if st.error and st.llm_ttft is None and st.skill_recall is None:
            print(_console(f"{case['id']:<12} ERROR: {st.error[:40]}"))
            continue
        err_mark = " *" if st.error else ""
        print(
            f"{case['id']:<12}{err_mark} "
            f"{_ms(st.skill_route):>8} {_ms(st.retrieval_plan):>8} "
            f"{_ms(st.rag_retrieve):>9} {_ms(st.skill_recall):>8} "
            f"{_ms(st.llm_ttft):>9} {_ms(st.agent_ttft):>9} {_ms(st.agent_total):>10}"
        )

    print("-" * 72)
    all_st = [st for _, st in rows if st.llm_ttft is not None or st.skill_recall is not None]
    if not all_st:
        return
    print(
        f"{'AVG':<12} "
        f"{_ms(_avg([s.skill_route for s in all_st])):>8} "
        f"{_ms(_avg([s.retrieval_plan for s in all_st])):>8} "
        f"{_ms(_avg([s.rag_retrieve for s in all_st])):>9} "
        f"{_ms(_avg([s.skill_recall for s in all_st])):>8} "
        f"{_ms(_avg([s.llm_ttft for s in all_st])):>9} "
        f"{_ms(_avg([s.agent_ttft for s in all_st])):>9} "
        f"{_ms(_avg([s.agent_total for s in all_st])):>10}"
    )

    print("\n解读:")
    avg_llm = _avg([s.llm_ttft for s in all_st]) or 0
    avg_recall = _avg([s.skill_recall for s in all_st]) or 0
    avg_agent = _avg([s.agent_ttft for s in all_st]) or 0
    avg_plan = _avg([s.retrieval_plan for s in all_st]) or 0
    avg_retrieve = _avg([s.rag_retrieve for s in all_st if s.rag_retrieve is not None]) or 0

    if avg_llm >= max(avg_recall, avg_agent) * 0.5:
        print("  - 模型/API 首 token 占比较高 -> 换更快模型、更近的 API 区域、或降 temperature/stream 参数")
    if avg_plan > avg_retrieve and avg_plan > 0.8:
        print("  - Retrieval Planner LLM 偏慢 -> Planner 是优化重点")
    if avg_retrieve > avg_plan and avg_retrieve > 1.0:
        print("  - 向量检索+精排偏慢 -> 查 pgvector、嵌入批大小、精排 top_k")
    if avg_recall > avg_llm and avg_recall > 1.0:
        print("  - Workflow(skill_recall) 整体慢于模型基线 -> Agent 管线是主因")
    if avg_agent > avg_llm + avg_recall * 0.8:
        print("  - Agent 首 token 约等于 Workflow + 模型，体感慢多为叠加延迟")


async def run_benchmark(args: argparse.Namespace) -> int:
    llm = llm_config()
    print("=== Agent 延迟诊断 ===")
    print(f"模型: {llm.get('model')} | base_url: {llm.get('base_url')}")
    print(f"样本数: {len(args.cases_list)} | warmup={args.warmup}")

    if not llm.get("api_key"):
        print("FAIL: 未配置 LLM api_key")
        return 1

    if not args.yes:
        est = len(args.cases_list) * 8
        ans = input(f"预计约 {est}+ 次 LLM/嵌入调用，继续? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消")
            return 0

    reset_knowledge_agent_cache()
    await init_checkpointer()
    get_stream_agent_executor(temperature=0.45, enable_web_search=False)

    if args.warmup:
        print("\n==> 预热 skill 短语缓存 + 向量库...")
        warmup_skill_phrase_cache()
        try:
            search_hits("OpenClaw 是什么", corpus=CORPUS_AGENT, top_k=1)
        except Exception as e:  # noqa: BLE001
            print(f"  WARN: 向量预热失败: {e}")

    rows: list[tuple[dict[str, str], StageTimes]] = []
    try:
        for i, case in enumerate(args.cases_list, start=1):
            if not args.quiet:
                print(f"\n######## [{i}/{len(args.cases_list)}] ########")
            st = await benchmark_one(case, run_idx=i)
            rows.append((case, st))
            if not args.quiet:
                _print_case_detail(case, st)
        _print_summary(rows)
    finally:
        await close_checkpointer()

    errors = sum(1 for _, st in rows if st.error)
    if errors:
        print(f"\nWARN: {errors} 题存在错误（若 agent 阶段失败，Workflow/llm 数据仍可参考）")
    return 1 if errors and not any(st.llm_ttft for _, st in rows) else 0


def _filter_cases(case_ids: str | None, limit: int | None) -> list[dict[str, str]]:
    cases = BENCH_CASES
    if case_ids:
        wanted = {x.strip() for x in case_ids.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
    if limit is not None:
        cases = cases[:limit]
    return cases


def main() -> None:
    p = argparse.ArgumentParser(description="Agent 分阶段延迟诊断")
    p.add_argument("--cases", type=str, default=None, help="逗号分隔 case id，如 greeting,knowledge")
    p.add_argument("--limit", type=int, default=None, help="只跑前 N 题")
    p.add_argument("--warmup", action="store_true", help="预热 skill 缓存与向量库")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出汇总")
    p.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    args = p.parse_args()
    args.cases_list = _filter_cases(args.cases, args.limit)
    if not args.cases_list:
        print("无匹配样本，可选 id: " + ", ".join(c["id"] for c in BENCH_CASES))
        raise SystemExit(1)
    raise SystemExit(asyncio.run(run_benchmark(args)))


if __name__ == "__main__":
    main()
