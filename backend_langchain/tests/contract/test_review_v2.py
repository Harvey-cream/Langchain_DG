import pytest
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from products.contract.domain.document import CanonicalContractClause
from products.contract.schemas.analysis import ReviewResult, validate_findings
from products.contract.agents.review import ReviewGraphResult


def clauses(version_id=None):
    version_id = version_id or uuid4()
    return (
        CanonicalContractClause(
            uuid4(),
            version_id,
            1,
            "付款",
            "payment",
            "甲方在签约当日支付全部价款。",
            (uuid4(),),
        ),
        CanonicalContractClause(
            uuid4(),
            version_id,
            2,
            "交付",
            "delivery",
            "乙方可无限延期交付。",
            (uuid4(),),
        ),
    )


def finding(clause, **changes):
    return dict(
        clause_id=str(clause.id),
        risk_type="payment",
        risk_level="high",
        evidence=clause.original_text,
        reason="付款先于交付",
        recommendation="明确付款条件",
        **changes,
    )


def test_v2_schema_allows_multiple_risks_and_empty_output():
    source = clauses()
    result = ReviewResult.model_validate(
        {"risks": [finding(source[0]), finding(source[0])]}
    )
    assert len(validate_findings(result, source, source[0].version_id).risks) == 2
    assert validate_findings(ReviewResult(), source, source[0].version_id).risks == []


@pytest.mark.parametrize(
    "change",
    [
        dict(clause_id=str(uuid4())),
        dict(evidence="编造"),
        dict(risk_level="HIGH"),
        dict(reason="  "),
        dict(original_text="生成条款"),
        dict(related_clause_ids=[str(uuid4())]),
    ],
)
def test_v2_rejects_bad_structured_output_or_grounding(change):
    source = clauses()
    risk = finding(source[0]) | change
    with pytest.raises(ValueError):
        validate_findings(
            ReviewResult.model_validate({"risks": [risk]}), source, source[0].version_id
        )


def test_v2_rejects_wrong_version_and_extra_clause_output():
    source = clauses()
    with pytest.raises(ValueError):
        validate_findings(ReviewResult(), source, uuid4())
    with pytest.raises(ValueError):
        ReviewResult.model_validate({"risks": [], "clauses": []})


def test_reviewer_inputs_existing_clauses_and_stance_only_outputs_risks():
    from products.contract.agents.review import ReviewAgent, ReviewLimits

    source = clauses()
    invoke = AsyncMock(return_value={"risks": [finding(source[0])]})
    model = SimpleNamespace(
        with_structured_output=lambda schema, **kw: SimpleNamespace(ainvoke=invoke)
    )
    result = asyncio.run(
        ReviewAgent(model, limits=ReviewLimits(react_enabled=False)).review(
            source, metadata={"parties": ["甲方", "乙方"]}, our_party="甲方"
        )
    )
    payload = json.loads(invoke.call_args.args[0][1].content)
    assert payload["our_party"] == "甲方"
    assert payload["targets"][0]["clause_id"] == str(source[0].id)
    assert payload["targets"][0]["original_text"] == source[0].original_text
    assert not hasattr(result, "clauses")


@pytest.mark.parametrize(
    "value", ["abcdefghij" * 7000, '付款\n\t"\\' * 9000], ids=["plain", "escaped"]
)
def test_review_windows_bound_input_without_dropping_long_clause_text(value):
    from dataclasses import replace
    from products.contract.agents.review.windows import (
        review_windows,
        MAX_REVIEW_INPUT_CHARS,
    )

    source = clauses()
    source = (replace(source[0], original_text=value), source[1])
    windows = list(review_windows(source, {"summary": "s" * 50000}, ""))
    assert all(
        len(json.dumps(w, ensure_ascii=False, separators=(",", ":")))
        <= MAX_REVIEW_INPUT_CHARS
        for w in windows
    )
    text = "".join(
        t["original_text"]
        for w in windows
        for t in w["targets"]
        if t["clause_id"] == str(source[0].id)
    )
    assert text == source[0].original_text


def test_agent_retries_bad_evidence_once_and_allows_no_risks():
    from products.contract.agents.review import ReviewAgent, ReviewLimits

    source = clauses()
    invoke = AsyncMock(
        side_effect=[
            {"risks": [finding(source[0]) | {"evidence": "捏造"}]},
            {"risks": []},
        ]
    )
    model = SimpleNamespace(
        with_structured_output=lambda schema, **kw: SimpleNamespace(ainvoke=invoke)
    )
    assert not asyncio.run(
        ReviewAgent(model, limits=ReviewLimits(react_enabled=False)).review(
            source, metadata={}
        )
    ).risks
    assert invoke.await_count == 2


def test_upload_flushes_parent_version_before_run_with_real_foreign_keys(
    document_db, monkeypatch
):
    from fastapi import BackgroundTasks, UploadFile
    from io import BytesIO
    from sqlalchemy import select
    from products.contract import api
    from products.contract.models import ContractVersionModel, AnalysisRunModel

    factory, existing_id = document_db
    writes = []
    storage = SimpleNamespace(
        put=lambda *args, **kwargs: writes.append(args[0]),
        delete=lambda key: (_ for _ in ()).throw(
            AssertionError("No failed upload cleanup expected")
        ),
    )
    monkeypatch.setattr(api, "OssObjectStorage", lambda: storage)
    monkeypatch.setattr(api, "validate_file", lambda *_: "pdf")

    async def check():
        async with factory() as session:
            async with session.begin():
                contract_id = (
                    await session.get(ContractVersionModel, existing_id)
                ).contract_id
            tasks = BackgroundTasks()
            response = await api.upload(
                contract_id,
                tasks,
                UploadFile(filename="test.pdf", file=BytesIO(b"%PDF-fictitious")),
                SimpleNamespace(user_id=1),
                session,
                our_party="甲方",
                party_role="supplier",
                contract_type="sales",
            )
            async with session.begin():
                version = await session.scalar(
                    select(ContractVersionModel).where(
                        ContractVersionModel.contract_id == contract_id,
                        ContractVersionModel.number == 2,
                    )
                )
                run = await session.scalar(
                    select(AnalysisRunModel).where(
                        AnalysisRunModel.version_id == version.id
                    )
                )
                assert (
                    run
                    and run.party_role == "supplier"
                    and run.contract_type == "sales"
                )
                assert json.loads(response.body)["data"]["run_id"] == str(run.id)
                assert len(tasks.tasks) == len(writes) == 1

    asyncio.run(check())


async def seed_facts(session, version_id):
    from products.contract import db
    from products.contract.domain.document import (
        DocumentBlock,
        ParsedDocument,
        DocumentFacts,
    )
    from products.contract.document_intelligence.clauses import ground_candidates
    from products.contract.document_intelligence.validation import validate_clauses
    from products.contract.schemas.document import ClauseCandidate

    blocks = tuple(
        DocumentBlock(uuid4(), version_id, i, text)
        for i, text in enumerate(
            ["甲方在签约当日支付全部价款。", "乙方可无限延期交付。"], 1
        )
    )
    canonical = ground_candidates(
        version_id,
        blocks,
        [
            ClauseCandidate(
                title="付款" if i == 0 else "交付", source_block_ids=[b.block_id]
            )
            for i, b in enumerate(blocks)
        ],
    )
    parsed = ParsedDocument(
        version_id, "\n\n".join(b.text for b in blocks), blocks, None, "python-docx"
    )
    facts = DocumentFacts(
        parsed,
        canonical,
        dict(
            summary="版本事实",
            parties=["甲方", "乙方"],
            amount="100元",
            duration="一年",
            payment_terms="预付款",
        ),
        validate_clauses(version_id, blocks, canonical),
    )
    return await db.save_document_facts(session, facts)


async def seed_run(session, version_id, *, status="analyzing", attempt=1):
    from products.contract.models import AnalysisRunModel

    run = AnalysisRunModel(
        id=uuid4(),
        version_id=version_id,
        status=status,
        attempt=attempt,
        review_version="v2",
        our_party="甲方",
        prompt_version="review-v2",
    )
    session.add(run)
    await session.flush()
    return run


def test_v2_atomic_publication_multiple_risks_and_idempotence(document_db):
    from sqlalchemy import select, func
    from products.contract import db
    from products.contract.domain.review import ReviewContext
    from products.contract.models import (
        ContractClauseModel,
        ContractRiskModel,
        ContractReviewSelectionModel,
    )

    factory, vid = document_db

    async def check():
        async with factory() as session:
            async with session.begin():
                facts = await seed_facts(session, vid)
                run = await seed_run(session, vid)
            context = ReviewContext(run.id, vid, "key", "x.docx")
            result = ReviewResult.model_validate(
                {
                    "risks": [
                        finding(facts.clauses[0]),
                        finding(facts.clauses[0])
                        | {"risk_type": "refund", "reason": "未约定退款条件"},
                    ]
                }
            )
            async with session.begin():
                await db.complete_run(session, context, result)
            async with session.begin():
                ids = list((await session.scalars(select(ContractRiskModel.id))).all())
                rows = (await session.scalars(select(ContractRiskModel))).all()
                assert len(ids) == 2
                assert all(
                    r.clause_id is None and r.canonical_clause_id == facts.clauses[0].id
                    for r in rows
                )
                assert (
                    await session.scalar(
                        select(func.count()).select_from(ContractClauseModel)
                    )
                    == 0
                )
                second = await seed_run(session, vid, attempt=2)
                await db.complete_run(
                    session,
                    ReviewContext(second.id, vid, "key", "x.docx"),
                    ReviewResult(),
                )
            async with session.begin():
                await db.complete_run(session, context, result)
                await db.fail_run(session, run.id, "重复执行者的迟到失败")
                assert (
                    list((await session.scalars(select(ContractRiskModel.id))).all())
                    == ids
                )
                selection = await session.get(ContractReviewSelectionModel, vid)
                assert selection.run_id == second.id
                assert run.status == "completed"

    asyncio.run(check())


@pytest.mark.parametrize(
    "status", ["pending", "parsing", "analyzing", "completed", "failed"]
)
def test_failure_only_transitions_active_runs(document_db, status):
    from products.contract import db
    from products.contract.models import ContractVersionModel

    factory, vid = document_db

    async def check():
        async with factory() as session:
            async with session.begin():
                facts = await seed_facts(session, vid)
                run = await seed_run(session, vid, status=status)
                run.error = "original"
                version = await session.get(ContractVersionModel, vid)
                version.status = status
            async with session.begin():
                await db.fail_run(session, run.id, "late failure")
            async with session.begin():
                await session.refresh(run)
                await session.refresh(version)
                active = status in ("pending", "parsing", "analyzing")
                assert run.status == ("failed" if active else status)
                assert version.status == ("failed" if active else status)
                assert run.error == ("late failure" if active else "original")
                assert (run.finished_at is not None) == active
                assert await db.get_document_facts(session, vid) == facts

    asyncio.run(check())


@pytest.mark.parametrize(
    "bad", ["unknown", "foreign_clause", "wrong_context", "bad_evidence"]
)
def test_persistence_rejects_invalid_association_without_partial_rows(document_db, bad):
    from dataclasses import replace
    from sqlalchemy import func, select
    from products.contract import db
    from products.contract.models import ContractVersionModel, ContractRiskModel
    from products.contract.domain.review import ReviewContext

    factory, vid = document_db

    async def check():
        async with factory() as session:
            async with session.begin():
                facts = await seed_facts(session, vid)
                run = await seed_run(session, vid)
                version = await session.get(ContractVersionModel, vid)
                other_vid = uuid4()
                session.add(
                    ContractVersionModel(
                        id=other_vid,
                        contract_id=version.contract_id,
                        number=2,
                        source_key="test2",
                        filename="other.docx",
                    )
                )
                await session.flush()
                other = await seed_facts(session, other_vid)
            risk = finding(facts.clauses[0])
            if bad == "unknown":
                risk["clause_id"] = str(uuid4())
            if bad == "foreign_clause":
                risk["clause_id"] = str(other.clauses[0].id)
            if bad == "bad_evidence":
                risk["evidence"] = "编造原文"
            context = ReviewContext(
                run.id, other_vid if bad == "wrong_context" else vid, "key", "x.docx"
            )
            with pytest.raises(ValueError):
                async with session.begin():
                    await db.complete_run(
                        session, context, ReviewResult.model_validate({"risks": [risk]})
                    )
            async with session.begin():
                assert (
                    await session.scalar(
                        select(func.count()).select_from(ContractRiskModel)
                    )
                    == 0
                )

    asyncio.run(check())


def test_publication_failure_rolls_back_findings_but_preserves_facts(document_db):
    from unittest.mock import patch
    from sqlalchemy import select, func
    from products.contract import db
    from products.contract.models import (
        AnalysisRunModel,
        ContractRiskModel,
        ContractReviewSelectionModel,
    )
    from products.contract.workflows.review_workflow import run_contract_review

    factory, vid = document_db

    async def check():
        async with factory() as session:
            async with session.begin():
                facts = await seed_facts(session, vid)
                run = await seed_run(session, vid, status="pending")
                run_id = run.id
            execute = session.execute

            async def broken(statement, *args, **kwargs):
                if (
                    getattr(getattr(statement, "table", None), "name", None)
                    == "contract_review_selections"
                ):
                    raise RuntimeError("publication failed after findings flush")
                return await execute(statement, *args, **kwargs)

            pipeline = SimpleNamespace(ensure=AsyncMock(return_value=facts))
            reviewer = SimpleNamespace(
                review=AsyncMock(
                    return_value=ReviewGraphResult(
                        ReviewResult.model_validate(
                            {"risks": [finding(facts.clauses[0])]}
                        )
                    )
                )
            )
            with patch.object(session, "execute", broken):
                await run_contract_review(session, pipeline, reviewer, run_id)
            async with session.begin():
                stored = await session.get(AnalysisRunModel, run_id)
                await session.refresh(stored)
                assert stored.status == "failed" and stored.result is None
                assert stored.finished_at is not None
                assert (
                    await session.scalar(
                        select(func.count()).select_from(ContractRiskModel)
                    )
                    == 0
                )
                assert await session.get(ContractReviewSelectionModel, vid) is None
                assert await db.get_document_facts(session, vid) == facts

    asyncio.run(check())


def test_v1_history_keeps_legacy_clauses_while_v2_reuses_version_facts(document_db):
    from sqlalchemy import select
    from products.contract import db
    from products.contract.models import (
        AnalysisRunModel,
        ContractClauseModel,
        ContractRiskModel,
        ContractVersionModel,
    )
    from products.contract.domain.review import ReviewContext
    from products.contract.api import _snapshot_payload

    factory, vid = document_db

    async def check():
        async with factory() as session:
            async with session.begin():
                facts = await seed_facts(session, vid)
                old = AnalysisRunModel(
                    id=uuid4(),
                    version_id=vid,
                    status="completed",
                    review_version="v1",
                    document_text="旧解析原文",
                    result={"summary": "历史摘要", "risks": []},
                )
                session.add(old)
                await session.flush()
                legacy_id = uuid4()
                session.add(
                    ContractClauseModel(
                        id=legacy_id,
                        version_id=vid,
                        run_id=old.id,
                        sequence=1,
                        title="历史条款",
                        clause_type="other",
                        original_text="旧解析原文",
                    )
                )
                await session.flush()
                session.add(
                    ContractRiskModel(
                        version_id=vid,
                        run_id=old.id,
                        clause_id=legacy_id,
                        title="旧风险",
                        risk_level="low",
                        evidence_text="旧解析原文",
                        reason="旧原因",
                        suggestion="旧建议",
                    )
                )
                new = await seed_run(session, vid, attempt=2)
                await db.complete_run(
                    session, ReviewContext(new.id, vid, "key", "x.docx"), ReviewResult()
                )
                contract_id = (await session.get(ContractVersionModel, vid)).contract_id
            async with session.begin():
                new_payload = _snapshot_payload(
                    await db.load_snapshot(session, 1, contract_id, vid)
                )
                assert (
                    new_payload["review_version"] == "v2" and new_payload["risks"] == []
                )
                assert await db.select_run(session, 1, contract_id, vid, old.id)
                old_payload = _snapshot_payload(
                    await db.load_snapshot(session, 1, contract_id, vid)
                )
                assert old_payload["review_version"] == "v1"
                assert old_payload["clauses"][0]["id"] == str(legacy_id)
                assert old_payload["risks"][0]["clause_id"] == str(legacy_id)
                assert old_payload["document_text"] == "旧解析原文"
                assert (
                    old_payload["canonical_clauses"] == new_payload["canonical_clauses"]
                )
                assert old_payload["facts"] == new_payload["facts"]
                assert await db.load_snapshot(session, 999, contract_id, vid) is None
                assert not await db.select_run(session, 999, contract_id, vid, new.id)

    asyncio.run(check())


def test_v2_api_facts_history_retry_stance_and_ownership(document_db):
    import httpx
    from fastapi import FastAPI
    from unittest.mock import patch
    from products.contract import api, db
    from common.database import get_db
    from common.auth.dependencies import require_user
    from products.contract.models import ContractVersionModel
    from products.contract.domain.review import ReviewContext

    factory, vid = document_db
    app = FastAPI()
    app.include_router(api.router)

    async def database():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[require_user] = lambda: SimpleNamespace(user_id=1)

    async def check():
        async with factory() as session, session.begin():
            facts = await seed_facts(session, vid)
            row = await seed_run(session, vid)
            first_id = row.id
            await db.complete_run(
                session,
                ReviewContext(row.id, vid, "key", "x.docx"),
                ReviewResult.model_validate({"risks": [finding(facts.clauses[0])]}),
            )
            version = await session.get(ContractVersionModel, vid)
            cid = version.contract_id
            version.source_key = f"contracts/1/{cid}/{vid}/original.docx"
        base = f"/api/contracts/{cid}/versions/{vid}"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            report = (await client.get(base + "/analysis")).json()["data"]
            assert report["review_version"] == "v2" and report["our_party"] == "甲方"
            assert report["facts"]["metadata"]["summary"] == "版本事实"
            assert report["clauses"] == []
            assert (
                report["canonical_clauses"][0]["id"] == report["risks"][0]["clause_id"]
            )
            assert report["risks"][0]["evidence"] == facts.clauses[0].original_text
            with patch.object(api, "execute_analysis", AsyncMock()):
                response = await client.post(
                    base + "/analyze", json={"our_party": "乙方"}
                )
                assert response.status_code == 200
                second_id = response.json()["data"]["run_id"]
                assert second_id != str(first_id)
                running = (await client.get(base + "/analysis")).json()["data"]
                assert (
                    running["latest_run_id"] == second_id
                    and running["status"] == "pending"
                )
                assert running["selected_run_id"] == str(first_id)
                repeat = await client.post(
                    base + "/analyze", json={"our_party": "乙方"}
                )
                assert repeat.json()["data"]["run_id"] == second_id
                assert (
                    await client.post(base + "/analyze", json={"our_party": "甲方"})
                ).status_code == 409
                assert (
                    await client.post(base + "/analyze", json={"our_party": "X" * 256})
                ).status_code == 422
                assert (
                    await client.post(base + "/analyze", json={"unexpected": True})
                ).status_code == 422
            history = (await client.get(base + "/analysis-runs")).json()["data"]["runs"]
            assert len(history) == 2 and all(
                r["review_version"] == "v2" for r in history
            )
            selected = (
                await client.post(base + f"/analysis-runs/{first_id}/select")
            ).json()["data"]
            assert selected["canonical_clauses"] == report["canonical_clauses"]
            app.dependency_overrides[require_user] = lambda: SimpleNamespace(
                user_id=999
            )
            assert (await client.get(base + "/analysis")).status_code == 404
            assert (await client.post(base + "/analyze")).status_code == 404
            assert (
                await client.post(base + f"/analysis-runs/{first_id}/select")
            ).status_code == 404

    asyncio.run(check())


def test_real_concurrent_claims_take_a_pending_run_once(document_db):
    from products.contract import db

    factory, vid = document_db

    async def check():
        async with factory() as session, session.begin():
            run = await seed_run(session, vid, status="pending")
            run_id = run.id

        async def claim():
            async with factory() as session, session.begin():
                return await db.claim_run(session, run_id)

        outcomes = await asyncio.gather(claim(), claim())
        assert sum(result is not None for result in outcomes) == 1
        assert next(result for result in outcomes if result).our_party == "甲方"

    asyncio.run(check())


def test_downgrade_refuses_to_erase_v2_review_data(document_db):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    factory, vid = document_db

    async def seed():
        async with factory() as session, session.begin():
            await seed_run(session, vid, status="completed")

    asyncio.run(seed())
    url = str(factory.kw["bind"].url).replace("sqlite+aiosqlite:", "sqlite:")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    with pytest.raises(RuntimeError, match="Review V2 数据存在"):
        command.downgrade(config, "0005_document_facts")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "0006_review_v2"
            )
            assert (
                conn.scalar(
                    text(
                        "SELECT COUNT(*) FROM contract_analysis_runs WHERE review_version='v2'"
                    )
                )
                == 1
            )
    finally:
        engine.dispose()
