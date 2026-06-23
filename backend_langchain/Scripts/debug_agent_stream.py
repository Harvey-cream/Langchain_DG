"""复现 LangGraph 异步流式；打印完整异常栈。"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root))

from Langchain_Agent.agents import get_stream_agent_executor, stream_agent
from Langchain_Agent.prompts import wrap_agent_user_message
from common.agent import init_checkpointer, warmup_agent_executors

THREAD = "debug:cli:1"
PROMPT = wrap_agent_user_message(
    "Say hello in one short English sentence. Do not use tools.",
)


async def main() -> None:
    print("--- init checkpointer ---")
    await init_checkpointer()
    print("--- warmup ---")
    try:
        warmup_agent_executors()
        print("ok")
    except Exception:
        traceback.print_exc()
        return

    print("--- stream_agent ---")
    try:
        get_stream_agent_executor()
        n = 0
        async for evt in stream_agent(prompt_text=PROMPT, thread_id=THREAD, temperature=0.45):
            n += 1
            print("evt", n, evt)
            if n >= 15:
                print("...(truncated)")
                break
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
