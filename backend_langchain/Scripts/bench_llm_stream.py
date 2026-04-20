"""直连 LLM_AGENT_* 流式压测：首包时间与总时长（与 Queue._quick_llm_stream_to_queue 同配置）。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from langchain_core.messages import HumanMessage

from config.config import LLM_AGENT_API_KEY, LLM_AGENT_BASE_URL, LLM_AGENT_MODEL, get_qwen_chat_model


def _piece(chunk: object) -> str:
    c = getattr(chunk, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out: list[str] = []
        for b in c:
            if isinstance(b, str):
                out.append(b)
            elif isinstance(b, dict) and b.get("text"):
                out.append(str(b["text"]))
        return "".join(out)
    return str(c)


def main() -> None:
    print(f"base_url={LLM_AGENT_BASE_URL!r} model={LLM_AGENT_MODEL!r} key_len={len(LLM_AGENT_API_KEY)}")
    llm = get_qwen_chat_model(streaming=True)
    msgs = [HumanMessage(content="你好，只回一句问候，不要超过20个字。")]
    t0 = time.perf_counter()
    t_first: float | None = None
    n = 0
    for chunk in llm.stream(msgs):
        n += 1
        if t_first is None and _piece(chunk).strip():
            t_first = time.perf_counter()
    t1 = time.perf_counter()
    print(f"chunks={n} first_chunk_s={(t_first - t0) if t_first else -1:.3f} total_s={t1 - t0:.3f}")


if __name__ == "__main__":
    main()
