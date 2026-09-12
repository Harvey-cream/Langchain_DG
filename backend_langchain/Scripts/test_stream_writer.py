"""诊断 get_stream_writer / runnable context 问题。

用法（在 backend_langchain 目录）：
    .venv\\Scripts\\python.exe Scripts\\test_stream_writer.py
    .venv\\Scripts\\python.exe Scripts\\test_stream_writer.py --live
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path
from typing import Annotated, Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

PASS = "OK"
FAIL = "FAIL"
SKIP = "SKIP"


def _ver(pkg: str) -> str:
    try:
        import importlib.metadata as md

        return md.version(pkg)
    except Exception:
        return "?"


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


async def _run_case(name: str, coro) -> str:
    print(f"\n--- {name} ---")
    try:
        await coro()
        print(f"  => {PASS}")
        return PASS
    except Exception as e:
        print(f"  => {FAIL}: {type(e).__name__}: {e}")
        tb = traceback.format_exc().strip().splitlines()
        for line in tb[-4:]:
            print(f"     {line}")
        return FAIL


class State(TypedDict):
    messages: Annotated[list, add_messages]


def _build_graph(*, agent_mode: str, with_tool: bool = False, sync_node: bool = False):
    """agent_mode: entry | in_astream | ainvoke | no_writer"""
    from config.config import get_qwen_chat_model

    model = get_qwen_chat_model(temperature=0.3, streaming=True)
    tools_list: list[Any] = []
    if with_tool:

        @tool
        def echo_tool(text: str) -> str:
            """回显输入文本，用于流式诊断。"""
            try:
                get_stream_writer()({"type": "status", "text": "tool-writer"})
            except Exception as e:
                return f"tool-writer-error: {e}"
            return f"echo:{text}"

        tools_list = [echo_tool]
        model = model.bind_tools(tools_list)

    system = SystemMessage(content="你是助手。尽量简短回答。")

    async def agent_node_async(state: State) -> dict:
        return await _run_agent(state)

    def agent_node_sync(state: State) -> dict:
        msgs = [system, *state["messages"]]
        writer = get_stream_writer()
        gathered = None
        for chunk in model.stream(msgs):
            content = getattr(chunk, "content", None)
            text = content if isinstance(content, str) else str(content or "")
            if text:
                writer({"type": "delta", "text": text[:80]})
            gathered = chunk if gathered is None else gathered + chunk
        if gathered is None:
            return {"messages": []}
        return {"messages": [gathered]}

    async def _run_agent(state: State) -> dict:
        msgs = [system, *state["messages"]]
        if agent_mode == "no_writer":
            reply = await model.ainvoke(msgs)
            return {"messages": [reply]}

        if agent_mode == "ainvoke":
            reply = await model.ainvoke(msgs)
            text = reply.content if isinstance(reply.content, str) else str(reply.content)
            if text:
                get_stream_writer()({"type": "delta", "text": text[:80]})
            return {"messages": [reply]}

        gathered = None
        if agent_mode == "entry":
            writer = get_stream_writer()
            async for chunk in model.astream(msgs):
                content = getattr(chunk, "content", None)
                text = content if isinstance(content, str) else str(content or "")
                if text:
                    writer({"type": "delta", "text": text[:80]})
                gathered = chunk if gathered is None else gathered + chunk
        else:  # in_astream：与当前 common/agent.py 相同
            async for chunk in model.astream(msgs):
                content = getattr(chunk, "content", None)
                text = content if isinstance(content, str) else str(content or "")
                if text:
                    get_stream_writer()({"type": "delta", "text": text[:80]})
                gathered = chunk if gathered is None else gathered + chunk

        if gathered is None:
            return {"messages": []}
        return {"messages": [gathered]}

    agent_node = agent_node_sync if sync_node else agent_node_async

    g = StateGraph(State)
    g.add_node("agent", agent_node)
    if tools_list:
        g.add_node("tools", ToolNode(tools_list))
    g.add_edge(START, "agent")
    if tools_list:
        g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        g.add_edge("tools", "agent")
    else:
        g.add_edge("agent", END)
    return g.compile()


async def _stream_graph(graph, user_text: str, *, stream_modes: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {"custom": 0, "messages": 0, "updates": 0, "errors": 0}
    async for mode, payload in graph.astream(
        {"messages": [HumanMessage(content=user_text)]},
        {"configurable": {"thread_id": "diag-test"}},
        stream_mode=stream_modes,
    ):
        counts[mode] = counts.get(mode, 0) + 1
        if mode == "custom":
            print(f"  custom: {payload!r}")
        elif mode == "messages":
            chunk = payload[0] if isinstance(payload, tuple) and payload else payload
            text = getattr(chunk, "content", chunk)
            print(f"  messages: {str(text)[:60]!r}")
    return counts


async def main(live: bool) -> int:
    _print_header("环境")
    py = sys.version_info
    print(f"  Python     : {py.major}.{py.minor}.{py.micro} ({sys.executable})")
    if py < (3, 11):
        print("  [WARN] Python < 3.11: LangGraph async get_stream_writer() 不可用（contextvar 不传播）")
    for pkg in ("langgraph", "langchain-core", "langchain-openai", "langgraph-checkpoint-postgres"):
        print(f"  {pkg:28}: {_ver(pkg)}")

    results: dict[str, str] = {}

    async def case_outside_graph():
        get_stream_writer()
        raise AssertionError("outside graph should not succeed")

    r = await _run_case("A. get_stream_writer() 在图外（应失败）", case_outside_graph)
    results["A_outside"] = PASS if r == FAIL else FAIL  # 预期失败

    if not live:
        _print_header("跳过 live 测试（加 --live 调用真实 LLM）")
        print("  仅完成环境 + 图外调用检查。")
        return 0

    async def case_entry():
        g = _build_graph(agent_mode="entry", with_tool=False)
        c = await _stream_graph(g, "说一个字：好", stream_modes=["custom"])
        print(f"  custom events: {c.get('custom', 0)}")
        if c.get("custom", 0) < 1:
            raise RuntimeError("no custom events")

    async def case_in_astream():
        g = _build_graph(agent_mode="in_astream", with_tool=False)
        c = await _stream_graph(g, "说一个字：好", stream_modes=["custom"])
        print(f"  custom events: {c.get('custom', 0)}")
        if c.get("custom", 0) < 1:
            raise RuntimeError("no custom events")

    async def case_messages_mode():
        g = _build_graph(agent_mode="ainvoke", with_tool=False)
        c = await _stream_graph(g, "说一个字：好", stream_modes=["messages", "custom"])
        print(f"  messages={c.get('messages', 0)} custom={c.get('custom', 0)}")

    async def case_tool_sync():
        g = _build_graph(agent_mode="in_astream", with_tool=True)
        c = await _stream_graph(
            g,
            "请调用 echo_tool，参数 text=hi，然后根据工具结果回复 ok",
            stream_modes=["custom", "updates"],
        )
        print(f"  custom={c.get('custom', 0)} updates={c.get('updates', 0)}")

    async def case_messages_only():
        g = _build_graph(agent_mode="no_writer", with_tool=False)
        c = await _stream_graph(g, "说一个字：好", stream_modes=["messages"])
        print(f"  messages events: {c.get('messages', 0)}")
        if c.get("messages", 0) < 1:
            raise RuntimeError("no messages events")

    async def case_sync_entry():
        g = _build_graph(agent_mode="entry", with_tool=False, sync_node=True)
        c = await _stream_graph(g, "说一个字：好", stream_modes=["custom"])
        print(f"  custom events: {c.get('custom', 0)}")
        if c.get("custom", 0) < 1:
            raise RuntimeError("no custom events")

    async def case_sync_stream_api():
        import concurrent.futures

        g = _build_graph(agent_mode="entry", with_tool=False, sync_node=True)

        def _run_sync_stream() -> int:
            n = 0
            for mode, payload in g.stream(
                {"messages": [HumanMessage(content="说一个字：好")]},
                {"configurable": {"thread_id": "diag-sync-stream"}},
                stream_mode=["custom"],
            ):
                if mode == "custom":
                    n += 1
                    print(f"  custom: {payload!r}")
            return n

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            n = await loop.run_in_executor(pool, _run_sync_stream)
        print(f"  custom events: {n}")
        if n < 1:
            raise RuntimeError("no custom events via sync stream()")

    for name, coro in [
        ("B. async 节点 + writer 在入口（entry）", case_entry),
        ("C. async 节点 + writer 在 astream 循环内（当前 agent.py）", case_in_astream),
        ("D. async 节点 + ainvoke 后 writer", case_messages_mode),
        ("G. 仅 messages 模式（不用 writer）", case_messages_only),
        ("H. sync 节点 + astream 调用（仍失败）", case_sync_entry),
        ("I. sync 节点 + graph.stream 在线程中", case_sync_stream_api),
        ("E. 同步工具内 get_stream_writer + ToolNode", case_tool_sync),
    ]:
        results[name.split(".")[0]] = await _run_case(name, coro)

    _print_header("汇总")
    for k, v in results.items():
        print(f"  {k}: {v}")

    print(
        "\n解读：\n"
        "  - B/C/D 全挂、G 过 → Python 3.10 async 无法用 get_stream_writer（根因）\n"
        "  - H 挂、I 过 → 3.10 下只有 sync stream() 能用 writer；FastAPI 用 astream 则不行\n"
        "  - G 过 → 推荐改用 stream_mode=messages 收 token\n"
        "  - E 挂 → 同步工具内也不能调 get_stream_writer\n"
        "  - F 复现线上路径"
    )
    failed = [k for k, v in results.items() if v == FAIL]
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="诊断 LangGraph get_stream_writer")
    parser.add_argument(
        "--live",
        action="store_true",
        help="调用真实 LLM 跑 B–F（需要 .env 里 LLM 配置可用）",
    )
    raise SystemExit(asyncio.run(main(parser.parse_args().live)))
