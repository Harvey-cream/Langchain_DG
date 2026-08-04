"""Memory Agent 子图：异步后置写长期记忆（不进对话 Supervisor，无 checkpointer）。

流程：START → trigger → extract → apply → END
  trigger 无价值 / extract 无候选时提前 END。
  apply 内对每条候选：search → decide（Pydantic）→ upsert。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import NotRequired

from agent.graphs.agents.memory.prompts import DECIDE_SYSTEM, EXTRACT_SYSTEM
from agent.graphs.agents.memory.schemas import DecideResult, ExtractResult, MemoryCandidate
from agent.memory.long_term_store import get_long_term_store
from agent.memory.long_term_trigger import should_run_memory_agent
from backend_langchain.logger_func import log_info_event, log_warning_event
from config.config import get_qwen_chat_model

logger = logging.getLogger(__name__)


class MemoryAgentState(TypedDict):
    user_id: int
    user_text: str
    assistant_text: str
    trigger_pass: NotRequired[bool]
    candidates: NotRequired[list[dict[str, Any]]]
    written: NotRequired[list[dict[str, str]]]


def build_memory_agent_graph() -> CompiledStateGraph:
    """编译 Memory Agent 图（无 checkpointer；由 schedule 异步 ainvoke）。"""

    async def trigger_node(state: MemoryAgentState) -> dict[str, Any]:
        ok = should_run_memory_agent(
            user_text=state.get("user_text") or "",
            assistant_text=state.get("assistant_text") or "",
        )
        log_info_event(
            logger,
            "memory_trigger_pass" if ok else "memory_trigger_skip",
            user_id=state.get("user_id"),
        )
        return {"trigger_pass": ok}

    async def extract_node(state: MemoryAgentState) -> dict[str, Any]:
        user_text = (state.get("user_text") or "").strip()[:2000]
        assistant_text = (state.get("assistant_text") or "")[:1500]
        llm = get_qwen_chat_model(temperature=0.1, streaming=False)
        structured = llm.with_structured_output(ExtractResult)
        try:
            result: ExtractResult = await structured.ainvoke(
                [
                    SystemMessage(content=EXTRACT_SYSTEM),
                    HumanMessage(content=f"用户：{user_text}\n助手：{assistant_text}"),
                ]
            )
        except Exception as e:  # noqa: BLE001
            log_warning_event(
                logger,
                "memory_extract_failed",
                user_id=state.get("user_id"),
                error=str(e),
            )
            return {"candidates": []}

        cands = [c.model_dump() for c in (result.candidates or [])[:5]]
        if not cands:
            log_info_event(logger, "memory_extract_empty", user_id=state.get("user_id"))
        return {"candidates": cands}

    async def apply_node(state: MemoryAgentState) -> dict[str, Any]:
        user_id = int(state.get("user_id") or 0)
        raw = state.get("candidates") or []
        store = get_long_term_store()
        written: list[dict[str, str]] = []
        decide_llm = get_qwen_chat_model(temperature=0.0, streaming=False)
        decide_structured = decide_llm.with_structured_output(DecideResult)

        for item in raw:
            try:
                cand = MemoryCandidate.model_validate(item)
            except Exception:  # noqa: BLE001
                continue

            similar = await asyncio.to_thread(
                store.search, cand.content, user_id=user_id, k=5
            )

            if not similar:
                decision = DecideResult(
                    action="insert", memory_key=cand.memory_key, reason="no_similar"
                )
            else:
                sim_lines = "\n".join(
                    f"- key={s.memory_key} type={s.memory_type} content={s.content}"
                    for s in similar[:5]
                )
                payload = (
                    f"候选：key={cand.memory_key} type={cand.memory_type} "
                    f"content={cand.content} importance={cand.importance}\n"
                    f"已有相似：\n{sim_lines}"
                )
                try:
                    decision = await decide_structured.ainvoke(
                        [
                            SystemMessage(content=DECIDE_SYSTEM),
                            HumanMessage(content=payload),
                        ]
                    )
                except Exception as e:  # noqa: BLE001
                    log_warning_event(
                        logger,
                        "memory_decide_failed",
                        user_id=user_id,
                        memory_key=cand.memory_key,
                        error=str(e),
                    )
                    continue

            if decision.action == "ignore":
                log_info_event(
                    logger,
                    "memory_decision_ignore",
                    user_id=user_id,
                    memory_key=decision.memory_key,
                    reason=decision.reason,
                )
                continue

            key = (decision.memory_key or cand.memory_key).strip()[:128]
            applied = await asyncio.to_thread(
                store.upsert,
                user_id=user_id,
                memory_key=key,
                memory_type=cand.memory_type,
                content=cand.content,
                importance=cand.importance,
            )
            log_info_event(
                logger,
                "memory_written",
                user_id=user_id,
                memory_key=key,
                action=decision.action,
                applied=applied,
            )
            written.append(
                {"memory_key": key, "action": decision.action, "applied": applied}
            )

        return {"written": written}

    def _after_trigger(state: MemoryAgentState) -> Literal["extract", "__end__"]:
        return "extract" if state.get("trigger_pass") else "__end__"

    def _after_extract(state: MemoryAgentState) -> Literal["apply", "__end__"]:
        return "apply" if state.get("candidates") else "__end__"

    builder = StateGraph(MemoryAgentState)
    builder.add_node("trigger", trigger_node)
    builder.add_node("extract", extract_node)
    builder.add_node("apply", apply_node)
    builder.add_edge(START, "trigger")
    builder.add_conditional_edges(
        "trigger", _after_trigger, {"extract": "extract", "__end__": END}
    )
    builder.add_conditional_edges(
        "extract", _after_extract, {"apply": "apply", "__end__": END}
    )
    builder.add_edge("apply", END)
    return builder.compile()
