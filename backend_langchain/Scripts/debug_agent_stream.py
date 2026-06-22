"""复现 LangGraph 流式；打印完整异常栈。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root))

from Langchain_Agent.agents import get_stream_agent_executor, stream_agent
from common.agent import warmup_agent_executors
from Langchain_Agent.prompts import wrap_agent_user_message

THREAD = "debug:cli:1"
PROMPT = wrap_agent_user_message(
    "Say hello in one short English sentence. Do not use tools.",
)


def main() -> None:
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
        for evt in stream_agent(
            prompt_text=PROMPT, thread_id=THREAD, temperature=0.45
        ):
            n += 1
            print("evt", n, evt)
            if n >= 15:
                print("...(truncated)")
                break
        print("stream ok, printed", n)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
