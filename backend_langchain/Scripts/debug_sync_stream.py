import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage

from common.agent import _merge_graph_config, get_cached_agent_executor
from Langchain_Agent.utils.answer_format_prompt import wrap_inline_tool_user_message

agent = get_cached_agent_executor(streaming=True)
prompt = wrap_inline_tool_user_message(
    "Say hello in one short English sentence. Do not use tools.",
    "",
    "",
)
cfg = _merge_graph_config(None, thread_id="dbg:sync:1")
inp = {"messages": [HumanMessage(content=prompt)]}
n = 0
for chunk in agent.stream(inp, cfg, stream_mode="messages"):
    n += 1
    print(n, type(chunk), repr(chunk)[:400])
    if n >= 12:
        break
print("total_printed", n)
