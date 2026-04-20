"""复现 LangGraph 流式 / 同步 invoke；打印完整异常栈。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root))

from common.agent import (
    _invoke_agent_sync,
    get_cached_agent_executor,
    warmup_agent_executors,
)
from Langchain_Agent.main_agent import stream_agent
from Langchain_Agent.utils.answer_format_prompt import wrap_inline_tool_user_message

THREAD = "debug:cli:1"
PROMPT = wrap_inline_tool_user_message(
    "Say hello in one short English sentence. Do not use tools.",
    memory_context="",
    skill_context="",
)


def main() -> None:
    print("--- 1) warmup_agent_executors ---")
    try:
        warmup_agent_executors()
        print("ok")
    except Exception:
        traceback.print_exc()
        return

    print("--- 2) sync invoke (streaming=False graph) ---")
    try:
        agent = get_cached_agent_executor(streaming=False)
        out = _invoke_agent_sync(agent, PROMPT, thread_id=THREAD)
        print("output:", (out.get("output") or "")[:200])
    except Exception:
        traceback.print_exc()
        return

    print("--- 3) stream_agent (streaming graph, sync messages stream) ---")
    try:
        n = 0
        for evt in stream_agent(
            prompt_text=PROMPT, thread_id=THREAD + ":stream", temperature=0.45
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
