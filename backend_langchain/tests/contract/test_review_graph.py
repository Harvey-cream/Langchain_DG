"""Real StateGraph/ToolNode tests; external model and retrieval responses are explicit fakes."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolInvocationError

import pytest

from products.contract.agents.review import ReviewAgent, ReviewLimits
from products.contract.quality import ReviewQualityError
from products.contract import retrieval
from products.contract.agents.review.tools import REVIEW_TOOLS
from test_review_v2 import clauses, finding


def fixed_agent(response):
    invoke = AsyncMock(return_value=response)
    model = SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=invoke)
    )
    return ReviewAgent(model, limits=ReviewLimits(react_enabled=False)), invoke


def test_fixed_graph_preserves_multiple_risks_and_explainable_dedupe():
    source = clauses()
    first = finding(source[0])
    second = first | {"recommendation": "另一个建议"}
    agent, invoke = fixed_agent({"risks": [first, first, second]})
    output = asyncio.run(agent.review(source, metadata={}))
    assert len(output.risks) == 2
    assert len(output.publication_result.risks) == 3
    assert output.quality_report["duplicate_count"] == 1
    assert output.review_trace["model_calls"][0]["phase"] == "generate"
    assert invoke.await_count == 1


@pytest.mark.parametrize(
    "text", ["甲方付款。", "甲方支付全部价款。" * 2500], ids=["single", "long"]
)
def test_fixed_graph_covers_every_source_character_and_allows_no_risks(text):
    source = clauses()
    source = (replace(source[0], original_text=text),)
    agent, invoke = fixed_agent({"risks": []})
    output = asyncio.run(agent.review(source, metadata={}))
    spans = [t for w in output.review_trace["windows"] for t in w["targets"]]
    assert sum(t["length"] for t in spans) == len(text)
    assert [t["source_offset"] for t in spans] == sorted(
        t["source_offset"] for t in spans
    )
    assert {t["clause_id"] for t in spans} == {str(source[0].id)}
    assert invoke.await_count == len(output.review_trace["windows"])
    assert output.risks == []


def test_graph_rejects_foreign_version_before_model_and_retries_bad_evidence():
    source = clauses()
    agent, invoke = fixed_agent({"risks": [finding(source[0]) | {"evidence": "伪造"}]})
    with pytest.raises(ReviewQualityError):
        asyncio.run(agent.review(source, metadata={}, version_id=uuid4()))
    assert invoke.await_count == 0
    with pytest.raises(ReviewQualityError) as error:
        asyncio.run(agent.review(source, metadata={}))
    assert invoke.await_count == 2
    assert len(error.value.review_trace["model_calls"]) == 2
    assert "上次质量校验失败" in invoke.call_args.args[0][-1].content


def tool_call(name, args, call_id="call-1"):
    return AIMessage(content="", tool_calls=[dict(name=name, args=args, id=call_id)])


class ScriptedModel:
    def __init__(self, decisions, generate=None):
        self.decide = AsyncMock(side_effect=decisions)
        self.generate = (
            AsyncMock(side_effect=generate)
            if generate
            else AsyncMock(return_value={"risks": []})
        )

    def bind_tools(self, tools, **kwargs):
        assert {t.name for t in tools} == {"search_knowledge", "get_related_clauses"}
        return SimpleNamespace(ainvoke=self.decide)

    def with_structured_output(self, *args, **kwargs):
        return SimpleNamespace(ainvoke=self.generate)


def reference(text="赔偿责任应设置上限。", owner=1):
    return dict(
        chunk_id=str(uuid4()),
        document_id=str(uuid4()),
        document_version=1,
        index_generation=1,
        owner_id=owner,
        filename="参考.docx",
        document_type="template",
        chunk_text=text,
        locator={"start_char": 0},
        embedding_model="test",
    )


def test_react_can_finish_without_tools_and_does_not_parse_decision_as_findings():
    model = ScriptedModel([AIMessage(content="已有资料足够。")])
    result = asyncio.run(ReviewAgent(model).review(clauses(), metadata={}, user_id=1))
    assert result.risks == [] and result.review_trace["tool_calls"] == []
    assert model.decide.await_count == model.generate.await_count == 1
    assert [c["phase"] for c in result.review_trace["model_calls"]] == [
        "decide",
        "generate",
    ]
    assert set(REVIEW_TOOLS[0].args) == {"query"}
    assert set(REVIEW_TOOLS[1].args) == {"clause_types"}


def test_real_toolnode_adds_supplementary_source_and_model_continues(monkeypatch):
    source, ref = clauses(), reference()
    search = AsyncMock(side_effect=[[], [ref]])
    monkeypatch.setattr(retrieval, "retrieve_references", search)

    async def generate(messages):
        payload = json.loads(messages[1].content)
        assert payload["references"][0]["chunk_id"] == ref["chunk_id"]
        return {
            "risks": [
                finding(source[0])
                | {
                    "reference_citations": [
                        dict(chunk_id=ref["chunk_id"], source_excerpt=ref["chunk_text"])
                    ]
                }
            ]
        }

    model = ScriptedModel(
        [
            tool_call("search_knowledge", {"query": "赔偿上限"}),
            AIMessage(content="足够"),
        ],
        generate,
    )
    output = asyncio.run(
        ReviewAgent(model, retrieval_factory=object()).review(
            source, metadata={}, user_id=1
        )
    )
    assert model.decide.await_count == 2 and search.await_count == 2
    second = model.decide.call_args_list[1].args[0]
    assert any(isinstance(m, ToolMessage) for m in second)
    assert ref["chunk_text"] in second[1].content
    assert output.used_references[0]["chunk_id"] == ref["chunk_id"]
    assert output.quality_report["status"] == "passed" and len(output.risks) == 1


def test_two_tool_rounds_share_query_cache_and_stop_at_limit(monkeypatch):
    ref = reference()
    search = AsyncMock(side_effect=[[], [ref]])
    monkeypatch.setattr(retrieval, "retrieve_references", search)
    model = ScriptedModel(
        [
            tool_call("search_knowledge", {"query": "赔偿上限"}, "one"),
            tool_call("search_knowledge", {"query": "  赔偿上限  "}, "two"),
        ]
    )
    output = asyncio.run(
        ReviewAgent(model, retrieval_factory=object()).review(
            clauses(), metadata={}, user_id=1
        )
    )
    assert search.await_count == 2 and model.decide.await_count == 2
    assert len(output.review_trace["tool_calls"]) == 2
    assert output.retrieval_events[-1]["cache_hit"] is True
    assert output.review_trace["limits_reached"]
    assert len(output.used_references) == 1


def test_related_tool_is_version_scoped_and_read_only():
    source = clauses()
    model = ScriptedModel(
        [
            tool_call("get_related_clauses", {"clause_types": [source[1].clause_type]}),
            AIMessage(content="可以审查"),
        ]
    )
    output = asyncio.run(ReviewAgent(model).review(source, metadata={}, user_id=1))
    call = output.review_trace["tool_calls"][0]
    assert str(source[1].id) in call["clause_ids"]
    assert model.decide.await_count == 2


@pytest.mark.parametrize(
    "name,args",
    [
        ("search_knowledge", {"query": "赔偿", "user_id": 2}),
        (
            "get_related_clauses",
            {"clause_types": ["payment"], "version_id": str(uuid4())},
        ),
        ("search_knowledge", {"query": "赔偿", "runtime": {"user_id": 2}}),
        ("execute_sql", {"sql": "DELETE FROM contracts"}),
        ("get_related_clauses", {"clause_types": ["made_up"]}),
    ],
    ids=["owner", "version", "runtime", "sql", "bad_type"],
)
def test_model_cannot_supply_scope_or_unapproved_tools(name, args):
    model = ScriptedModel([tool_call(name, args)])
    with pytest.raises((ValueError, ToolInvocationError)) as error:
        asyncio.run(ReviewAgent(model).review(clauses(), metadata={}, user_id=1))
    assert model.generate.await_count == 0 and error.value.review_trace


def test_requested_tool_count_over_budget_uses_existing_sources():
    response = AIMessage(
        content="",
        tool_calls=[
            dict(name="search_knowledge", args={"query": "资料"}, id=str(i))
            for i in range(5)
        ],
    )
    model = ScriptedModel([response])
    output = asyncio.run(ReviewAgent(model).review(clauses(), metadata={}, user_id=1))
    assert (
        not output.review_trace["tool_calls"] and output.review_trace["limits_reached"]
    )
    assert model.generate.await_count == 1


@pytest.mark.parametrize("bad", ["owner", "id", "timeout", "service"], ids=str)
def test_invalid_or_unavailable_tool_result_fails_safely(monkeypatch, bad):
    async def search(factory, owner, query, **kwargs):
        if "我方角色" in query:
            return []
        if bad == "timeout":
            await asyncio.sleep(1)
        if bad == "service":
            raise RuntimeError("service unavailable")
        ref = reference(owner=2 if bad == "owner" else 1)
        if bad == "id":
            ref["chunk_id"] = "fake"
        return [ref]

    monkeypatch.setattr(retrieval, "retrieve_references", search)
    model = ScriptedModel([tool_call("search_knowledge", {"query": "赔偿"})])
    with pytest.raises(Exception) as error:
        asyncio.run(
            ReviewAgent(
                model,
                retrieval_factory=object(),
                limits=ReviewLimits(tool_timeout=0.05),
            ).review(clauses(), metadata={}, user_id=1)
        )
    assert model.generate.await_count == 0
    assert error.value.review_trace["tool_calls"][0]["status"] == "failed"


def test_unsupported_tool_model_is_explicitly_rejected():
    agent, _ = fixed_agent({"risks": []})
    agent.limits = ReviewLimits()
    with pytest.raises(ValueError, match="不支持 Tool Calling"):
        asyncio.run(agent.review(clauses(), metadata={}, user_id=1))


def test_empty_tool_result_is_not_fabricated(monkeypatch):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(retrieval, "retrieve_references", search)
    model = ScriptedModel(
        [
            tool_call("search_knowledge", {"query": "不存在的依据"}),
            AIMessage(content="依据不足"),
        ]
    )
    output = asyncio.run(
        ReviewAgent(model, retrieval_factory=object()).review(
            clauses(), metadata={}, user_id=1
        )
    )
    assert output.used_references == [] and output.risks == []
    assert output.review_trace["tool_calls"][0]["reference_count"] == 0
    assert search.await_count == 2 and model.decide.await_count == 2


def test_baseline_cannot_expose_foreign_source_to_model(monkeypatch):
    monkeypatch.setattr(
        retrieval, "retrieve_references", AsyncMock(return_value=[reference(owner=2)])
    )
    model = ScriptedModel([])
    with pytest.raises(ReviewQualityError):
        asyncio.run(
            ReviewAgent(model, retrieval_factory=object()).review(
                clauses(), metadata={}, user_id=1
            )
        )
    assert model.decide.await_count == model.generate.await_count == 0


def test_same_agent_concurrent_reviews_do_not_share_scope_cache_or_trace(monkeypatch):
    calls = []

    async def search(factory, owner, query, **kwargs):
        calls.append((owner, query))
        await asyncio.sleep(0)
        return [reference(owner=owner)]

    monkeypatch.setattr(retrieval, "retrieve_references", search)
    model = ScriptedModel([])

    async def decide(messages):
        return (
            AIMessage(content="足够")
            if any(isinstance(m, ToolMessage) for m in messages)
            else tool_call("search_knowledge", {"query": "共同查询"})
        )

    model.decide.side_effect = decide
    agent, a, b = ReviewAgent(model, retrieval_factory=object()), clauses(), clauses()

    async def run():
        return await asyncio.gather(
            agent.review(a, metadata={}, user_id=1),
            agent.review(b, metadata={}, user_id=2),
        )

    outputs = asyncio.run(run())
    assert len(calls) == 4 and outputs[0].review_trace is not outputs[1].review_trace
    for owner, source, output in zip((1, 2), (a, b), outputs):
        assert all(r["owner_id"] == owner for r in output.used_references)
        assert set(output.used_references[0]["clause_ids"]) == {
            str(c.id) for c in source
        }
        assert len(output.review_trace["tool_calls"]) == 1


def test_tool_round_budget_and_history_reset_for_each_window():
    source = (replace(clauses()[0], original_text="付款条款。" * 6000),)
    model = ScriptedModel([])
    model.decide.side_effect = lambda messages: tool_call(
        "get_related_clauses", {"clause_types": ["payment"]}
    )
    limits = ReviewLimits(max_tool_rounds=1, max_tool_calls=1)
    output = asyncio.run(
        ReviewAgent(model, limits=limits).review(source, metadata={}, user_id=1)
    )
    count = len(output.review_trace["windows"])
    assert count > 1 and len(output.review_trace["tool_calls"]) == count
    assert model.decide.await_count == model.generate.await_count == count
    assert all(
        not any(isinstance(m, ToolMessage) for m in call.args[0])
        for call in model.decide.call_args_list
    )


def test_only_budget_admitted_source_prefix_is_citable():
    from products.contract.agents.review.nodes import add_references
    from products.contract.agents.review.windows import review_windows, encode

    source = clauses()
    window = next(review_windows(source, {}, ""))
    ref = reference("规则。" * 8000)
    packed, used = add_references(window, [], [ref], budget=3000)
    assert len(encode(packed)) <= 3000 and used
    assert len(used[0]["chunk_text"]) < len(ref["chunk_text"])
    assert ref["chunk_text"].startswith(used[0]["chunk_text"])
    assert packed["references"][0]["chunk_text"] == used[0]["chunk_text"]
    _, omitted = add_references(window, [], [ref], budget=10)
    assert omitted == []


@pytest.mark.parametrize("kind", ["model", "whole_review", "recursion"])
def test_time_and_recursion_budgets_preserve_failure_trace(kind):
    from langgraph.errors import GraphRecursionError

    source = (replace(clauses()[0], original_text="付款。" * 10000),)
    agent, invoke = fixed_agent({"risks": []})
    options = {}
    if kind == "recursion":
        agent.limits = ReviewLimits(react_enabled=False, recursion_limit=5)
        expected = GraphRecursionError
    else:

        async def slow(messages):
            await asyncio.sleep(1)
            return {"risks": []}

        invoke.side_effect = slow
        if kind == "model":
            agent.limits = ReviewLimits(react_enabled=False, model_timeout=0.02)
            expected = ValueError
        else:
            options["timeout_seconds"] = 0.02
            expected = TimeoutError
    with pytest.raises(expected) as error:
        asyncio.run(agent.review(source, metadata={}, **options))
    assert error.value.review_trace["elapsed_seconds"] >= 0
    # A whole-graph timeout may expire before the first model call on a busy host.
    assert (
        invoke.await_count <= 1 if kind == "whole_review" else invoke.await_count == 1
    )


@pytest.mark.parametrize(
    "failure",
    [None, "gate", "publication"],
    ids=["success", "bad_finding", "db_rollback"],
)
def test_tool_sources_and_findings_publish_atomically_and_remain_immutable(
    document_db, monkeypatch, failure
):
    from sqlalchemy import select, func
    from products.contract import db
    from products.contract.models import (
        AnalysisRunModel,
        ContractRiskModel,
        ContractKnowledgeChunkModel as Chunk,
        ContractKnowledgeDocumentModel as Document,
    )
    from products.contract.domain.review import ReviewContext
    from products.contract.knowledge import ingest_document
    from products.contract.workflows.review_workflow import run_contract_review
    from products.contract.schemas.analysis import ReviewResult
    from test_knowledge import MemoryStorage, FakeEmbeddings, seed_document, docx_bytes
    from test_review_v2 import seed_facts, seed_run

    factory, vid = document_db
    storage = MemoryStorage()

    async def check():
        async with factory() as session, session.begin():
            doc = await seed_document(session, storage, docx_bytes())
            did = doc.id
            facts = await seed_facts(session, vid)
            run = await seed_run(session, vid, status="pending")
            rid = run.id
        await ingest_document(
            did, 1, factory=factory, storage=storage, embeddings=FakeEmbeddings()
        )
        async with factory() as session:
            chunk = await session.scalar(select(Chunk).where(Chunk.document_id == did))
            ref = retrieval.reference_snapshot(chunk, await session.get(Document, did))
        monkeypatch.setattr(
            retrieval, "retrieve_references", AsyncMock(side_effect=[[], [ref]])
        )

        async def generate(messages):
            payload = json.loads(messages[1].content)
            assert payload["references"][0]["chunk_id"] == ref["chunk_id"]
            return {
                "risks": [
                    finding(facts.clauses[0])
                    | {
                        "reference_citations": [
                            dict(
                                chunk_id=ref["chunk_id"],
                                source_excerpt=ref["chunk_text"][:25],
                            )
                        ]
                    }
                ]
            }

        model = ScriptedModel(
            [
                tool_call("search_knowledge", {"query": "补充企业规范"}),
                AIMessage(content="足够"),
            ],
            generate,
        )
        agent = ReviewAgent(model, retrieval_factory=factory)
        output = None
        actual_review = agent.review

        async def capture(*args, **kwargs):
            nonlocal output
            output = await actual_review(*args, **kwargs)
            if failure == "gate":
                forged = output.risks[0].model_copy(update={"evidence": "编造证据"})
                return replace(output, raw_findings=[forged])
            return output

        monkeypatch.setattr(agent, "review", capture)
        async with factory() as session:
            execute = session.execute

            async def broken(statement, *args, **kwargs):
                if (
                    getattr(getattr(statement, "table", None), "name", None)
                    == "contract_review_selections"
                ):
                    raise RuntimeError("fail after references and findings")
                return await execute(statement, *args, **kwargs)

            if failure == "publication":
                monkeypatch.setattr(session, "execute", broken)
            await run_contract_review(
                session,
                SimpleNamespace(ensure=AsyncMock(return_value=facts)),
                agent,
                rid,
            )
        async with factory() as session, session.begin():
            stored = await session.get(AnalysisRunModel, rid)
            if failure:
                assert stored.status == "failed" and stored.result is None
                assert not stored.context_snapshot.get("references")
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(ContractRiskModel)
                        .where(ContractRiskModel.run_id == rid)
                    )
                    == 0
                )
                assert (
                    stored.context_snapshot["review_trace"]["tool_calls"][0]["status"]
                    == "passed"
                )
                if failure == "gate":
                    assert stored.context_snapshot["quality_gate"]["status"] == "failed"
                return
            assert (
                stored.status == "completed"
                and stored.context_snapshot["references"][0]["chunk_id"]
                == ref["chunk_id"]
            )
            snapshot, result = stored.context_snapshot, stored.result
            doc = await session.get(Document, did)
            doc.status = "deleted"
        async with factory() as session, session.begin():
            context = ReviewContext(rid, vid, "key", "test.docx", user_id=1)
            for reference in output.used_references:
                await db.record_review_references(
                    session, context, [reference], reference["clause_ids"]
                )
            await db.complete_run(session, context, output.publication_result)
            await db.fail_run(
                session,
                rid,
                "late failure",
                review_trace={"prompt_version": "wrong"},
                quality_error=ReviewQualityError("schema", "late"),
            )
            stored = await session.get(AnalysisRunModel, rid)
            assert (
                stored.status == "completed"
                and stored.context_snapshot == snapshot
                and stored.result == result
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ContractRiskModel)
                    .where(ContractRiskModel.run_id == rid)
                )
                == 1
            )
            with pytest.raises(ValueError):
                altered = output.used_references[0] | {"filename": "伪造.docx"}
                await db.record_review_references(
                    session, context, [altered], altered["clause_ids"]
                )

    asyncio.run(check())
