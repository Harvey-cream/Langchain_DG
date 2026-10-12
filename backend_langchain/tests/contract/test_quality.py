"""P4.8 deterministic gate and real SQLite persistence; external models are fake."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import func, select

from products.contract import db, retrieval
from products.contract.agents.review import ReviewAgent, ReviewLimits
from products.contract.agents.review.windows import review_windows
from products.contract.domain.review import ReviewContext, REVIEW_PROMPT_VERSION
from products.contract.models import (
    ContractRiskModel,
    ContractVersionModel,
)
from products.contract.quality import locate_excerpt, verify_review, ReviewQualityError
from products.contract.schemas.analysis import ReviewResult
from products.contract.workflows.review_workflow import run_contract_review
from test_review_v2 import clauses, finding, seed_facts, seed_run


@pytest.mark.parametrize(
    "source,excerpt,match",
    [
        ("乙方赔偿金额不设上限。", "赔偿金额不设上限", "exact"),
        ("Payment:  within\r\n  45 days.", "within 45 days", "unicode_whitespace"),
        ("付款金额\n不设上限。", "付款金额 不设上限", "unicode_whitespace"),
        ("cafe\u0301 payment", "café payment", "unicode_whitespace"),
        ("앞 가 뒤", "가", "exact"),
    ],
)
def test_evidence_locates_exact_source_with_safe_normalization(source, excerpt, match):
    span = locate_excerpt(source, excerpt)
    assert span["match"] == match
    assert source[span["start_char"] : span["end_char"]]


@pytest.mark.parametrize(
    "source,excerpt",
    [
        ("赔偿金额不设上限。", "赔偿责任不得超过合同金额"),
        ("not liable", "notliable"),
        ("付款90天", "付款45天"),
        ("不支持退款", "支持全额退款"),
        ("付款，交付", "付款交付"),
        ("上限为①元", "上限为1元"),
        ("金额\n不设上限", "金额不设上限"),
        ("café", "cafe"),
        ("责任无限", "   "),
    ],
)
def test_grounding_does_not_fuzzily_repair_hallucinations(source, excerpt):
    with pytest.raises(ReviewQualityError):
        locate_excerpt(source, excerpt)


def test_gate_normalizes_to_verbatim_evidence_and_preserves_locator():
    source = clauses()
    source = (replace(source[0], original_text="甲方在\r\n签约当日付款。"), source[1])
    risk = finding(source[0]) | {
        "evidence": "甲方在 签约当日付款。",
        "risk_type": " Payment-Risk ",
    }
    checked = verify_review({"risks": [risk]}, source, source[0].version_id)
    assert checked.result.risks[0].evidence == source[0].original_text
    assert checked.result.risks[0].risk_type == "payment_risk"
    assert checked.report["finding_checks"][0]["evidence_locator"]["start_char"] == 0
    assert (
        checked.report["normalizations"][0]["original"]["evidence"] == risk["evidence"]
    )


def test_normalized_citation_revalidates_actual_source_length():
    source = clauses()
    kid = uuid4()
    risk = finding(source[0]) | {
        "reference_citations": [dict(chunk_id=str(kid), source_excerpt="付款 期限")]
    }
    with pytest.raises(ReviewQualityError) as error:
        verify_review(
            {"risks": [risk]},
            source,
            source[0].version_id,
            references=[
                dict(
                    chunk_id=str(kid),
                    chunk_text="付款" + " " * 1200 + "期限",
                    clause_ids=[str(source[0].id)],
                )
            ],
        )
    assert error.value.code == "schema"


@pytest.mark.parametrize("response", [{}, ReviewResult()])
def test_model_must_explicitly_output_risks_including_empty_list(response):
    source = clauses()
    invoke = AsyncMock(return_value=response)
    reviewer = ReviewAgent(
        SimpleNamespace(
            with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=invoke)
        ),
        limits=ReviewLimits(react_enabled=False),
    )
    with pytest.raises(ReviewQualityError) as error:
        asyncio.run(reviewer.review(source, metadata={}))
    assert error.value.code == "schema" and invoke.await_count == 2


def test_dedupe_is_conservative_explainable_and_preserves_originals():
    source = clauses()
    risk = finding(source[0])
    risks = [
        risk,
        risk | {"risk_type": " PAYMENT "},
        risk | {"evidence": "支付全部价款。"},
        risk | {"recommendation": "另一个有效建议"},
        risk | {"related_clause_ids": [str(source[1].id)]},
    ]
    checked = verify_review({"risks": risks}, source, source[0].version_id)
    assert len(checked.result.risks) == 4 and checked.report["duplicate_count"] == 1
    assert (
        checked.report["duplicates"][0]["original"]
        == ReviewResult.model_validate({"risks": [risks[1]]}).model_dump(mode="json")[
            "risks"
        ][0]
    )
    assert checked.report["warnings"] and any(
        "保留变体" in note
        for c in checked.report["finding_checks"]
        for note in c["notes"]
    )
    cross = risk | {"related_clause_ids": [str(source[1].id)]}
    assert (
        len(
            verify_review(
                {"risks": [cross, cross]}, source, source[0].version_id
            ).result.risks
        )
        == 1
    )


@pytest.mark.parametrize(
    "change,code",
    [
        ({"clause_id": str(uuid4())}, "clause_grounding"),
        ({"evidence": "编造原文"}, "evidence_grounding"),
        ({"related_clause_ids": [str(uuid4())]}, "clause_grounding"),
        ({"policy_ids": [str(uuid4())]}, "policy_grounding"),
        (
            {
                "reference_citations": [
                    {"chunk_id": str(uuid4()), "source_excerpt": "编造依据"}
                ]
            },
            "rag_citation",
        ),
        ({"risk_level": "CRITICAL"}, "schema"),
        ({"reason": "  "}, "schema"),
        ({"recommendation": "  "}, "schema"),
        ({"contract_change_id": str(uuid4())}, "schema"),
        ({"approved_contract": "新的正式文本"}, "schema"),
        ({"reason": "依据 ContractChange 生成新的条款"}, "unapproved_revision"),
        ({"recommendation": "已批准替换合同中的本条款。"}, "unapproved_revision"),
    ],
)
def test_invalid_findings_fail_with_stable_quality_codes(change, code):
    source = clauses()
    with pytest.raises(ReviewQualityError) as error:
        verify_review(
            {"risks": [finding(source[0]) | change]}, source, source[0].version_id
        )
    assert error.value.code == code


def test_owner_scope_versions_and_citations_are_frozen_and_validated():
    source = clauses()
    pid, kid, did = uuid4(), uuid4(), uuid4()
    policy = dict(
        id=str(pid),
        owner_id=1,
        version=2,
        enabled=True,
        archived=False,
        applicable_party_role="buyer",
        applicable_contract_types=["procurement"],
        severity="high",
    )
    reference = dict(
        chunk_id=str(kid),
        owner_id=1,
        document_id=str(did),
        document_version=1,
        index_generation=3,
        chunk_text="企业付款期限\r\n 45天。",
        clause_ids=[str(source[0].id)],
    )
    risk = finding(source[0]) | {
        "policy_ids": [str(pid)],
        "reference_citations": [
            dict(chunk_id=str(kid), source_excerpt="付款期限 45天")
        ],
    }
    options = dict(
        policies=[policy],
        references=[reference],
        owner_id=1,
        party_role="buyer",
        contract_type="procurement",
    )
    checked = verify_review({"risks": [risk]}, source, source[0].version_id, **options)
    assert checked.report["finding_checks"][0]["policy_versions"] == [
        {"id": str(pid), "version": 2}
    ]
    assert (
        checked.result.risks[0].reference_citations[0].source_excerpt
        == "付款期限\r\n 45天"
    )
    for changed in [
        dict(owner_id=2),
        dict(version=0),
        dict(enabled=False),
        dict(applicable_party_role="supplier"),
    ]:
        with pytest.raises(ReviewQualityError):
            verify_review(
                {"risks": [risk]},
                source,
                source[0].version_id,
                **(options | {"policies": [policy | changed]}),
            )
    for changed in [
        dict(owner_id=2),
        dict(document_id="fake"),
        dict(document_version=0),
        dict(clause_ids=[str(source[1].id)]),
    ]:
        with pytest.raises(ReviewQualityError):
            verify_review(
                {"risks": [risk]},
                source,
                source[0].version_id,
                **(options | {"references": [reference | changed]}),
            )
    with pytest.raises(ReviewQualityError):
        verify_review({"risks": [risk]}, source, uuid4(), **options)


@pytest.mark.parametrize("field", ["reason", "recommendation"])
def test_legal_claims_and_unknown_types_become_explicit_review_hints(field):
    source = clauses()
    checked = verify_review(
        {
            "risks": [
                finding(source[0]) | {field: "该条款违法。", "risk_type": "<script>"}
            ]
        },
        source,
        source[0].version_id,
    )
    assert checked.result.risks[0].risk_type == "other"
    check = checked.report["finding_checks"][0]
    assert check["assessment"] == "insufficient_legal_basis" and check["notes"]
    assert (
        verify_review({"risks": []}, source, source[0].version_id).report["status"]
        == "passed"
    )


@pytest.mark.parametrize("bad", ["schema", "clause", "evidence", "policy", "reference"])
def test_agent_retries_invalid_output_only_twice_and_supplies_repair_feedback(bad):
    source = clauses()
    risk = finding(source[0])
    changes = {
        "schema": {"risk_level": "BAD"},
        "clause": {"clause_id": str(uuid4())},
        "evidence": {"evidence": "虚构"},
        "policy": {"policy_ids": [str(uuid4())]},
        "reference": {
            "reference_citations": [
                {"chunk_id": str(uuid4()), "source_excerpt": "虚构"}
            ]
        },
    }
    invoke = AsyncMock(return_value={"risks": [risk | changes[bad]]})
    model = SimpleNamespace(
        with_structured_output=lambda *args, **kwargs: SimpleNamespace(ainvoke=invoke),
        model_name="fake-model",
    )
    reviewer = ReviewAgent(model, limits=ReviewLimits(react_enabled=False))
    with pytest.raises(ReviewQualityError) as error:
        asyncio.run(reviewer.review(source, metadata={}))
    trace = error.value.review_trace
    assert invoke.await_count == 2 and len(trace["model_calls"]) == 2
    assert all(c["status"] == "rejected" for c in trace["model_calls"])
    assert "上次质量校验失败" in invoke.call_args.args[0][-1].content


def test_raw_structured_response_records_actual_model_and_retries_parser_failure():
    source = clauses()
    invoke = AsyncMock(
        side_effect=[
            {
                "parsed": None,
                "raw": AIMessage(
                    content="", response_metadata={"model_name": "actual-fallback"}
                ),
                "parsing_error": ValueError("bad"),
            },
            {
                "parsed": {"risks": [finding(source[0])]},
                "raw": AIMessage(
                    content="", response_metadata={"model_name": "actual-fallback"}
                ),
                "parsing_error": None,
            },
        ]
    )
    reviewer = ReviewAgent(
        SimpleNamespace(
            with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=invoke)
        ),
        limits=ReviewLimits(react_enabled=False),
    )
    output = asyncio.run(reviewer.review(source, metadata={}))
    trace = output.review_trace
    assert output.risks
    assert trace["model_calls"][1]["model"] == "actual-fallback"
    assert trace["model_calls"][0]["status"] == "rejected"


def test_structured_fallback_trace_does_not_mislabel_the_primary_model():
    from common.config.failover import FailoverLLM

    source = clauses()
    first = SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(
            ainvoke=AsyncMock(side_effect=RuntimeError("provider unavailable"))
        )
    )
    second = SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(
            ainvoke=AsyncMock(return_value={"risks": [finding(source[0])]})
        )
    )
    reviewer = ReviewAgent(
        FailoverLLM([first, second], labels=["primary", "real-fallback"]),
        limits=ReviewLimits(react_enabled=False),
    )
    output = asyncio.run(reviewer.review(source, metadata={}))
    trace = output.review_trace
    assert output.risks
    assert trace["model_calls"][0]["model"] == "real-fallback"


def test_reference_snapshot_issuance_checks_actual_chunk_document_and_owner(
    document_db,
):
    from test_knowledge import MemoryStorage, FakeEmbeddings, seed_document, docx_bytes
    from products.contract.knowledge import ingest_document
    from products.contract.models import (
        ContractKnowledgeChunkModel as Chunk,
        ContractKnowledgeDocumentModel as Document,
    )
    from common.account.models import User

    factory, vid = document_db
    storage, embedding = MemoryStorage(), FakeEmbeddings()

    async def check():
        async with factory() as session, session.begin():
            session.add(
                User(
                    user_id=2,
                    email="quality-other@test.invalid",
                    username="other",
                    password="fake",
                )
            )
            await session.flush()
            documents = [
                await seed_document(session, storage, docx_bytes(), owner_id=owner)
                for owner in (1, 2)
            ]
            ids = [d.id for d in documents]
        for did in ids:
            await ingest_document(
                did, 1, factory=factory, storage=storage, embeddings=embedding
            )
        async with factory() as session, session.begin():
            facts = await seed_facts(session, vid)
            run = await seed_run(session, vid)
            owned = await session.scalar(
                select(Chunk).where(Chunk.document_id == ids[0])
            )
            private = await session.scalar(
                select(Chunk).where(Chunk.document_id == ids[1])
            )
            reference = retrieval.reference_snapshot(
                owned, await session.get(Document, ids[0])
            )
            context = ReviewContext(run.id, vid, "key", "test.docx", user_id=1)
            for changed in [
                dict(document_id=str(ids[1])),
                dict(chunk_id=str(private.id)),
                dict(document_version=2),
            ]:
                with pytest.raises(ValueError):
                    await db.record_review_references(
                        session,
                        context,
                        [reference | changed],
                        [str(facts.clauses[0].id)],
                    )
            assert not run.context_snapshot
            stored = await db.record_review_references(
                session, context, [reference], [str(facts.clauses[0].id)]
            )
            assert stored["references"][0]["document_id"] == str(ids[0])

    asyncio.run(check())


def test_distant_payment_delivery_refund_context_is_reviewed_without_new_agent():
    from products.contract.domain.document import CanonicalContractClause

    vid = uuid4()
    source = tuple(
        CanonicalContractClause(
            uuid4(),
            vid,
            i,
            f"条款{i}",
            (
                "payment"
                if i == 2
                else "delivery" if i == 8 else "other" if i == 12 else "confidentiality"
            ),
            (
                "甲方签署后10日全额付款。"
                if i == 2
                else (
                    "乙方收款后90日交付。"
                    if i == 8
                    else "任何情况下均不支持退款。" if i == 12 else "保密义务。" * 500
                )
            ),
            (uuid4(),),
        )
        for i in range(1, 15)
    )
    windows = list(review_windows(source, {}, "甲方"))
    window = next(
        w
        for w in windows
        if str(source[1].id) in {t["clause_id"] for t in w["targets"]}
    )
    supplied = {t["clause_id"] for t in window["targets"] + window["context_clauses"]}
    assert {str(source[7].id), str(source[11].id)}.issubset(supplied)

    async def invoke(messages):
        payload = json.loads(messages[1].content)
        if str(source[1].id) not in {t["clause_id"] for t in payload["targets"]}:
            return {"risks": []}
        risk = finding(source[1]) | {
            "related_clause_ids": [str(source[7].id), str(source[11].id)]
        }
        return {"risks": [risk, risk]}

    model = SimpleNamespace(
        with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=invoke)
    )
    raw = asyncio.run(
        ReviewAgent(model, limits=ReviewLimits(react_enabled=False)).review(
            source, metadata={}
        )
    )
    result = verify_review(raw.publication_result, source, vid)
    assert (
        len(result.result.risks) == 1
        and len(result.result.risks[0].related_clause_ids) == 2
    )


def test_publication_revalidates_and_quality_failure_cannot_save_or_replace_history(
    document_db,
):
    factory, vid = document_db

    async def check():
        async with factory() as session, session.begin():
            facts = await seed_facts(session, vid)
            old = await seed_run(session, vid)
            risk = finding(facts.clauses[0])
            raw = ReviewResult.model_validate({"risks": [risk, risk]})
            await db.complete_run(
                session, ReviewContext(old.id, vid, "key", "test.docx"), raw
            )
            assert old.context_snapshot["quality_gate"]["duplicate_count"] == 1
            old_id, snapshot = old.id, old.context_snapshot
        invalid = AsyncMock(
            return_value={"risks": [risk | {"evidence": "伪造合同原文"}]}
        )
        reviewer = ReviewAgent(
            SimpleNamespace(
                with_structured_output=lambda *a, **k: SimpleNamespace(ainvoke=invalid),
                model_name="fake-review",
            ),
            limits=ReviewLimits(react_enabled=False),
        )
        async with factory() as session:
            async with session.begin():
                run = await seed_run(session, vid, status="pending", attempt=2)
            await run_contract_review(
                session,
                SimpleNamespace(ensure=AsyncMock(return_value=facts)),
                reviewer,
                run.id,
            )
            async with session.begin():
                await session.refresh(run)
                assert (
                    run.status == "failed"
                    and run.result is None
                    and "两次" in run.error
                )
                assert run.context_snapshot["quality_gate"]["status"] == "failed"
                assert len(run.context_snapshot["review_trace"]["model_calls"]) == 2
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(ContractRiskModel)
                        .where(ContractRiskModel.run_id == run.id)
                    )
                    == 0
                )
                cid = (await session.get(ContractVersionModel, vid)).contract_id
                selected = await db.load_snapshot(session, 1, cid, vid)
                assert (
                    selected.selected_run.id == old_id
                    and selected.selected_run.context_snapshot == snapshot
                )
                assert await db.get_document_facts(session, vid) == facts
        # A caller bypassing Agent/Workflow still cannot publish forged evidence.
        async with factory() as session:
            async with session.begin():
                run = await seed_run(session, vid, attempt=3)
            with pytest.raises(ReviewQualityError):
                async with session.begin():
                    await db.complete_run(
                        session,
                        ReviewContext(run.id, vid, "key", "test.docx"),
                        ReviewResult.model_validate(
                            {"risks": [risk | {"evidence": "伪造"}]}
                        ),
                    )

    asyncio.run(check())


def test_partial_reference_withdrawal_is_omitted_not_fabricated(document_db):
    from test_knowledge import MemoryStorage, FakeEmbeddings, seed_document, docx_bytes
    from products.contract.knowledge import ingest_document
    from products.contract.models import ContractKnowledgeDocumentModel as Document

    factory, _ = document_db
    storage, embedding = MemoryStorage(), FakeEmbeddings()

    async def check():
        async with factory() as session, session.begin():
            documents = [
                await seed_document(session, storage, docx_bytes("企业付款规则。"))
                for _ in range(2)
            ]
            dids = [d.id for d in documents]
        for did in dids:
            await ingest_document(
                did, 1, factory=factory, storage=storage, embeddings=embedding
            )
        loop = asyncio.get_running_loop()

        async def withdraw():
            async with factory() as session, session.begin():
                document = await session.get(Document, dids[0])
                document.status = "deleted"

        def rerank(query, texts, **kwargs):
            asyncio.run_coroutine_threadsafe(withdraw(), loop).result(timeout=5)
            return list(range(len(texts)))

        diagnostics = {}
        references = await retrieval.retrieve_references(
            factory,
            1,
            "付款",
            embeddings=embedding,
            reranker=rerank,
            diagnostics=diagnostics,
        )
        assert len(references) == 1 and references[0]["document_id"] == str(dids[1])
        assert diagnostics["unavailable_count"] == 1

    asyncio.run(check())
