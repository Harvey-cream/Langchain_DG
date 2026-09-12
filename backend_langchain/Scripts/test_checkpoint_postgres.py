"""验证 LangGraph checkpoint 写入独立 PostgreSQL 库 langchain_checkpoint。

用法（cwd=backend_langchain）:
  APP_ENV=debug python Scripts/test_checkpoint_postgres.py
"""
import asyncio
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _EchoState(TypedDict):
    messages: Annotated[list, add_messages]


async def main() -> int:
    import asyncpg
    from langchain_core.messages import HumanMessage
    from langgraph.graph import START, StateGraph

    from app.settings import (
        POSTGRES_CHECKPOINT_DATABASE,
        POSTGRES_HOST,
        POSTGRES_PASSWORD,
        POSTGRES_PORT,
        POSTGRES_USER,
    )
    from runtime.checkpoint.checkpointer import close_checkpointer, get_checkpointer, init_checkpointer

    print(f"host={POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"checkpoint_db={POSTGRES_CHECKPOINT_DATABASE}")

    await init_checkpointer()
    cp = get_checkpointer()

    async def _echo(state: _EchoState) -> dict:
        return {"messages": [HumanMessage(content="pong")]}

    g = StateGraph(_EchoState)
    g.add_node("echo", _echo)
    g.add_edge(START, "echo")
    app = g.compile(checkpointer=cp)

    thread_id = "test:checkpoint:postgres:1"
    cfg = {"configurable": {"thread_id": thread_id}}
    await app.ainvoke({"messages": [HumanMessage(content="ping")]}, cfg)

    snap = await app.aget_state(cfg)
    values = snap.values or {}
    msgs = values.get("messages") or []
    texts = [getattr(m, "content", None) for m in msgs]
    print("checkpoint messages:", texts)

    conn = await asyncpg.connect(
        host=POSTGRES_HOST,
        port=int(POSTGRES_PORT),
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_CHECKPOINT_DATABASE,
    )
    try:
        tables = [
            r[0]
            for r in await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
        ]
        print("tables:", tables)
        if "checkpoints" not in tables:
            print("FAIL: no checkpoints table")
            return 1
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id=$1", thread_id
        )
        print(f"checkpoints rows for {thread_id!r}: {n}")
        if int(n) < 1:
            print("FAIL: no checkpoint row written")
            return 1
    finally:
        await conn.close()
        await close_checkpointer()

    if "pong" not in str(texts):
        print("FAIL: graph state missing expected message")
        return 1

    print("OK: PostgreSQL checkpoint read/write verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
