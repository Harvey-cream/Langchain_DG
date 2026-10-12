"""The only model tools: owner-scoped knowledge search and current-Version clauses."""

import asyncio
from time import perf_counter
from typing import Literal

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field

from products.contract import retrieval
from products.contract.quality import verify_review
from .state import ReviewRuntime, ReviewState
from .windows import encode


class KnowledgeQuery(BaseModel):
    # ToolNode injects runtime before Pydantic validation. Public arguments are
    # strictly allowlisted in agent_decide BEFORE that server-side injection.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=500)


class ClauseQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    clause_types: list[
        Literal[
            "payment",
            "delivery",
            "acceptance",
            "refund",
            "termination",
            "breach",
            "amount",
            "term",
            "confidentiality",
            "intellectual_property",
            "dispute",
            "other",
        ]
    ] = Field(min_length=1, max_length=4)


async def search_references(
    context: ReviewRuntime, state: ReviewState, query: str, kind: str
):
    """One invocation-local cache; concurrent repeated calls share the same search."""
    started = perf_counter()
    event = dict(
        kind=kind,
        query=query,
        clause_ids=[c["clause_id"] for c in state["current_window"]["targets"]],
    )
    if context.retrieval_factory is None:
        return [], dict(event, reference_count=0, cache_hit=False, elapsed_seconds=0)
    if type(state["user_id"]) is not int or state["user_id"] <= 0:
        raise ValueError("知识库审查缺少用户权限范围")
    key = " ".join(query.split()).casefold()
    async with asyncio.timeout(context.limits.tool_timeout), context.query_lock:
        cache_hit = key in context.query_cache
        if not cache_hit:
            diagnostics = {}
            references = await asyncio.wait_for(
                retrieval.retrieve_references(
                    context.retrieval_factory,
                    state["user_id"],
                    query,
                    diagnostics=diagnostics,
                ),
                timeout=context.limits.tool_timeout,
            )
            context.query_cache[key] = (references, diagnostics)
        references, diagnostics = context.query_cache[key]
    event.update(diagnostics)
    event.update(
        reference_count=len(references),
        cache_hit=cache_hit,
        elapsed_seconds=round(perf_counter() - started, 3),
    )
    return references, event


@tool(args_schema=KnowledgeQuery, response_format="content_and_artifact")
async def search_knowledge(
    query: str, runtime: ToolRuntime[ReviewRuntime, ReviewState]
):
    """按额外业务问题检索当前用户私有知识库。返回真实来源；不要重复已有查询。"""
    state, context = runtime.state, runtime.context
    call = dict(
        id=runtime.tool_call_id,
        name="search_knowledge",
        query=query,
        window=state["window_index"],
        status="failed",
    )
    context.trace["tool_calls"].append(call)
    started = perf_counter()
    try:
        references, event = await search_references(
            context, state, query, "supplementary"
        )
        scoped = [dict(r, clause_ids=event["clause_ids"]) for r in references]
        verify_review(
            {"risks": []},
            state["clauses"],
            state["version_id"],
            references=scoped,
            owner_id=state["user_id"],
        )
        call.update(
            status="passed", reference_count=len(scoped), cache_hit=event["cache_hit"]
        )
        # ToolMessage acknowledges the call; its artifact is packed into the next
        # model's source payload once, avoiding duplicated long source transcripts.
        return encode({"retrieved_count": len(scoped)}), dict(
            references=scoped, event=event
        )
    except TimeoutError as exc:
        raise ValueError("补充知识库工具调用超时") from exc
    finally:
        call["elapsed_seconds"] = round(perf_counter() - started, 3)


@tool(args_schema=ClauseQuery, response_format="content_and_artifact")
async def get_related_clauses(
    clause_types: list[str], runtime: ToolRuntime[ReviewRuntime, ReviewState]
):
    """按条款类型读取当前合同版本的真实关联条款；refund 查退款文字，最多四条。"""
    state, context = runtime.state, runtime.context
    clauses, size = [], 0
    for clause in state["clauses"]:
        if clause.version_id != state["version_id"]:
            raise ValueError("关联条款越过当前合同版本")
        refund = "refund" in clause_types and any(
            word in clause.original_text.casefold()
            for word in ("退款", "退还", "refund")
        )
        if clause.clause_type not in clause_types and not refund:
            continue
        item = dict(
            clause_id=str(clause.id),
            title=clause.title,
            clause_type=clause.clause_type,
            original_text=clause.original_text[:4000],
        )
        if size + len(encode(item)) > 6000:
            continue
        clauses.append(item)
        size += len(encode(item))
        if len(clauses) == 4:
            break
    context.trace["tool_calls"].append(
        dict(
            id=runtime.tool_call_id,
            name="get_related_clauses",
            clause_types=clause_types,
            window=state["window_index"],
            status="passed",
            clause_ids=[c["clause_id"] for c in clauses],
        )
    )
    return encode({"clause_count": len(clauses)}), dict(clauses=clauses)


REVIEW_TOOLS = [search_knowledge, get_related_clauses]
