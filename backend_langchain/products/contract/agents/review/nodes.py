"""Business stages of one Review Graph; task/transaction lifecycle stays outside."""

import hashlib

from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

from products.contract import retrieval
from products.contract.quality import verify_review
from products.contract.schemas.analysis import ReviewResult
from .state import ReviewState, ReviewRuntime
from .tools import search_references, REVIEW_TOOLS
from .windows import review_windows, encode, MAX_REVIEW_INPUT_CHARS


def prepare_windows(state: ReviewState, runtime: Runtime[ReviewRuntime]):
    verify_review(
        {"risks": []},
        state["clauses"],
        state["version_id"],
        policies=state["policies"],
        owner_id=state["user_id"],
        party_role=state["party_role"],
        contract_type=state["contract_type"],
    )
    windows = list(
        review_windows(
            state["clauses"],
            state["metadata"],
            state["our_party"],
            policies=state["policies"],
            reserve_chars=6000,
            party_role=state["party_role"],
            contract_type=state["contract_type"],
        )
    )
    return dict(
        windows=windows,
        window_index=0,
        findings=[],
        used_references=[],
        retrieval_events=[],
        messages=Overwrite([]),
    )


def add_references(window, current, fetched, *, budget):
    """Pack only source prefixes actually provided to this window's model."""
    window = {**window, "references": list(window["references"])}
    references = list(current)
    existing = {r["chunk_id"] for r in references}
    targets = list(dict.fromkeys(t["clause_id"] for t in window["targets"]))
    for reference in fetched:
        if reference["chunk_id"] in existing:
            continue
        item = {**reference, "clause_ids": targets}
        prompt_reference = {
            key: item[key]
            for key in (
                "chunk_id",
                "document_id",
                "document_version",
                "filename",
                "document_type",
                "locator",
                "chunk_text",
            )
        }
        proposed = {**window, "references": window["references"] + [prompt_reference]}
        while len(encode(proposed)) > budget and len(item["chunk_text"]) > 200:
            item["chunk_text"] = item["chunk_text"][: len(item["chunk_text"]) // 2]
            prompt_reference["chunk_text"] = item["chunk_text"]
        if len(encode(proposed)) <= budget:
            references.append(item)
            existing.add(item["chunk_id"])
            window = proposed
    return window, references


def merge_references(existing, added):
    """Snapshots use prefix excerpts; retain the longest provided prefix and scopes."""
    merged = {r["chunk_id"]: dict(r) for r in existing}
    for reference in added:
        previous = merged.get(reference["chunk_id"])
        item = dict(reference)
        if previous:
            if not (
                previous["chunk_text"].startswith(item["chunk_text"])
                or item["chunk_text"].startswith(previous["chunk_text"])
            ):
                raise ValueError("同一知识库片段的来源文字在审查中发生变化")
            item["clause_ids"] = sorted(
                set(previous["clause_ids"]) | set(item["clause_ids"])
            )
            if len(previous["chunk_text"]) > len(item["chunk_text"]):
                item["chunk_text"] = previous["chunk_text"]
        merged[item["chunk_id"]] = item
    return list(merged.values())


async def retrieve_baseline(state: ReviewState, runtime: Runtime[ReviewRuntime]):
    window = state["windows"][state["window_index"]]
    query = retrieval.clause_query(
        window["targets"],
        party_role=state["party_role"],
        contract_type=state["contract_type"],
    )
    fetched, event = await search_references(
        runtime.context, {**state, "current_window": window}, query, "baseline"
    )
    # Leave room for bounded ToolCall/ToolMessage protocol when ReAct is enabled.
    budget = MAX_REVIEW_INPUT_CHARS - (
        3000 if runtime.context.limits.react_enabled else 0
    )
    window, references = add_references(window, [], fetched, budget=budget)
    verify_review(
        {"risks": []},
        state["clauses"],
        state["version_id"],
        references=references,
        owner_id=state["user_id"],
    )
    if fetched and not references:
        raise ValueError("检索资料超过审查上下文预算，请精简适用规则或参考资料")
    return dict(
        current_window=window,
        current_references=references,
        retrieval_events=state["retrieval_events"] + [event],
        messages=Overwrite([]),
        tool_rounds=0,
        tool_count=0,
        processed_tool_ids=[],
        tools_pending=False,
    )


def collect_tool_results(state: ReviewState):
    """Admit returned sources before the next decision/generation, with one budget."""
    window, references = state["current_window"], state["current_references"]
    events, processed, messages = (
        list(state["retrieval_events"]),
        list(state["processed_tool_ids"]),
        [],
    )
    for message in state["messages"]:
        if not isinstance(message, ToolMessage) or message.tool_call_id in processed:
            messages.append(message)
            continue
        artifact = message.artifact or {}
        window, references = add_references(
            window,
            references,
            artifact.get("references", []),
            budget=MAX_REVIEW_INPUT_CHARS - 3000,
        )
        provided = {
            c["clause_id"] for c in window["targets"] + window["context_clauses"]
        }
        added_ids = []
        for clause in artifact.get("clauses", []):
            if clause["clause_id"] in provided:
                continue
            proposed = {
                **window,
                "context_clauses": window["context_clauses"] + [clause],
            }
            if len(encode(proposed)) <= MAX_REVIEW_INPUT_CHARS - 3000:
                window = proposed
                provided.add(clause["clause_id"])
                added_ids.append(clause["clause_id"])
        if "event" in artifact:
            events.append(artifact["event"])
        content = encode(
            dict(
                context_updated=True,
                provided_chunk_ids=[r["chunk_id"] for r in references],
                added_clause_ids=added_ids,
            )
        )
        messages.append(
            message.model_copy(update={"content": content, "artifact": None})
        )
        processed.append(message.tool_call_id)
    return dict(
        current_window=window,
        current_references=references,
        retrieval_events=events,
        processed_tool_ids=processed,
        messages=messages,
    )


async def agent_decide(state: ReviewState, runtime: Runtime[ReviewRuntime]):
    updates = collect_tool_results(state)
    state = {**state, **updates}
    context, limits = runtime.context, runtime.context.limits
    updates["tools_pending"] = False
    if not limits.react_enabled:
        return {**updates, "messages": Overwrite(updates["messages"])}
    history_size = sum(
        len(encode(m.model_dump(mode="json"))) for m in state["messages"]
    )
    if (
        state["tool_rounds"] >= limits.max_tool_rounds
        or state["tool_count"] >= limits.max_tool_calls
        or len(encode(state["current_window"])) + history_size > MAX_REVIEW_INPUT_CHARS
    ):
        context.trace.setdefault("limits_reached", []).append(
            dict(window=state["window_index"], reason="tool_or_context_budget")
        )
        return {**updates, "messages": Overwrite(updates["messages"])}
    response = await context.llm.decide(state)
    calls = response.tool_calls
    if len(calls) > limits.max_tool_calls - state["tool_count"]:
        context.trace.setdefault("limits_reached", []).append(
            dict(
                window=state["window_index"],
                reason="too_many_requested_tools",
                requested=len(calls),
            )
        )
        return {**updates, "messages": Overwrite(updates["messages"])}
    allowed = {t.name: set(t.args) for t in REVIEW_TOOLS}
    seen_ids = set(state["processed_tool_ids"])
    for call in calls:
        if (
            call["name"] not in allowed
            or not isinstance(call["args"], dict)
            or not set(call["args"]).issubset(allowed[call["name"]])
        ):
            raise ValueError(
                "Review Tool 调用名称或参数越权；模型不能指定用户、版本或运行时"
            )
        if not call["id"] or call["id"] in seen_ids or len(call["id"]) > 200:
            raise ValueError("Review Tool 调用 ID 非法或重复")
        seen_ids.add(call["id"])
    updates.update(
        messages=Overwrite(state["messages"] + [response]),
        tools_pending=bool(calls),
        tool_rounds=state["tool_rounds"] + bool(calls),
        tool_count=state["tool_count"] + len(calls),
    )
    return updates


async def generate_findings(state: ReviewState, runtime: Runtime[ReviewRuntime]):
    window = state["current_window"]
    runtime.context.trace["windows"].append(
        dict(
            targets=[
                dict(
                    clause_id=t["clause_id"],
                    source_offset=t["source_offset"],
                    length=len(t["original_text"]),
                    sha256=hashlib.sha256(t["original_text"].encode()).hexdigest(),
                )
                for t in window["targets"]
            ],
            related_clause_ids=[c["clause_id"] for c in window["context_clauses"]],
            chunk_ids=[r["chunk_id"] for r in state["current_references"]],
            input_chars=len(encode(window)),
        )
    )
    result = await runtime.context.llm.generate(state)
    return dict(
        findings=state["findings"] + result.risks,
        used_references=merge_references(
            state["used_references"], state["current_references"]
        ),
        window_index=state["window_index"] + 1,
    )


def quality_gate(state: ReviewState):
    verified = verify_review(
        ReviewResult(risks=state["findings"]),
        state["clauses"],
        state["version_id"],
        policies=state["policies"],
        references=state["used_references"],
        owner_id=state["user_id"],
        party_role=state["party_role"],
        contract_type=state["contract_type"],
    )
    return dict(result=verified.result, quality_report=verified.report)
