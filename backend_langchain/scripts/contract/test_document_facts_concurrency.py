"""PostgreSQL fact publication concurrency on a disposable database only."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from common.account.models import User
from products.contract.models import (
    CanonicalContractClauseModel,
    ContractDocumentBlockModel,
    ContractDocumentFactsModel,
    ContractModel,
    ContractVersionModel,
    CustomerModel,
    AnalysisRunModel,
    ContractRiskModel,
    ContractClauseModel,
)
from products.contract import db as contract_db
from products.contract.document_intelligence.pipeline import (
    DocumentIntelligencePipeline,
)
from products.contract.domain.document import DocumentBlock, ParsedDocument
from products.contract.domain.review import ReviewContext
from products.contract.agents.review import ReviewGraphResult
from products.contract.schemas.document import (
    ClauseCandidate,
    ClauseExtraction,
    DocumentMetadata,
    SectionCandidate,
    SectionExtraction,
)
from scripts.contract.test_contract_migration_postgres import (
    BACKEND_ROOT,
    _drop_database,
    _psycopg_url,
    _url,
)
from common.settings import POSTGRES_DATABASE


class FakeDocumentCapabilities:
    async def sections(self, blocks):
        return SectionExtraction(
            sections=[
                SectionCandidate(
                    title="正文", source_block_ids=[b.block_id for b in blocks]
                )
            ]
        )

    async def clauses(self, blocks):
        return ClauseExtraction(
            clauses=[
                ClauseCandidate(
                    title="条款", source_block_ids=[b.block_id for b in blocks]
                )
            ]
        )

    async def metadata(self, blocks):
        return DocumentMetadata(summary="事实")


async def verify(database_name):
    engine = create_async_engine(
        _url(database_name).set(drivername="postgresql+asyncpg")
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    version_id, contract_id = uuid4(), uuid4()
    try:
        async with factory() as session, session.begin():
            session.add(
                User(
                    user_id=1,
                    username="facts",
                    email="facts@test.invalid",
                    password="test",
                )
            )
            await session.flush()
            session.add(
                CustomerModel(id=1, user_id=1, name="test", email="test@test.invalid")
            )
            await session.flush()
            session.add(
                ContractModel(id=contract_id, user_id=1, customer_id=1, title="test")
            )
            await session.flush()
            session.add(
                ContractVersionModel(
                    id=version_id,
                    contract_id=contract_id,
                    number=1,
                    filename="test.pdf",
                    source_key="unused",
                )
            )

        both_parsing = asyncio.Event()
        parse_calls = 0
        block = DocumentBlock(uuid4(), version_id, 1, "第一条 真实原文", page=1)
        parsed = ParsedDocument(version_id, block.text, (block,), 1, "pdfplumber")

        async def parse(context):
            nonlocal parse_calls
            parse_calls += 1
            if parse_calls == 2:
                both_parsing.set()
            await asyncio.wait_for(both_parsing.wait(), timeout=10)
            return parsed

        async def publish():
            async with factory() as session:
                pipeline = DocumentIntelligencePipeline(
                    session,
                    SimpleNamespace(parse=parse),
                    FakeDocumentCapabilities(),
                )
                return await pipeline.ensure(
                    ReviewContext(uuid4(), version_id, "unused", "test.pdf")
                )

        first, second = await asyncio.gather(publish(), publish())
        assert first == second
        assert (
            parse_calls == 2
        )  # Both passed the initial cache miss before either published.
        async with factory() as session:
            for model in (
                ContractDocumentBlockModel,
                CanonicalContractClauseModel,
                ContractDocumentFactsModel,
            ):
                assert (
                    await session.scalar(select(func.count()).select_from(model)) == 1
                )
            assert await contract_db.get_document_facts(session, version_id) == first
        print(
            "PostgreSQL concurrent Document Facts publishers: one identical fact set, passed",
            flush=True,
        )
        # Review callbacks, concurrent retry requests and duplicate publishers use real row locks.
        from fastapi import BackgroundTasks
        from products.contract.api import analyze
        from products.contract.schemas.api import ReviewRequest
        from products.contract.schemas.analysis import ReviewResult, RiskFinding
        from products.contract.workflows.review_workflow import run_contract_review

        async with factory() as session, session.begin():
            version = await session.get(ContractVersionModel, version_id)
            version.source_key = f"contracts/1/{contract_id}/{version_id}/original.pdf"

        async def retry():
            async with factory() as session:
                background = BackgroundTasks()
                response = await analyze(
                    contract_id,
                    version_id,
                    background,
                    SimpleNamespace(user_id=1),
                    session,
                    ReviewRequest(our_party="甲方"),
                )
                import json

                return json.loads(response.body)["data"]["run_id"], len(
                    background.tasks
                )

        retries = await asyncio.gather(retry(), retry())
        assert retries[0][0] == retries[1][0] and sum(r[1] for r in retries) == 1
        from uuid import UUID

        run_id = UUID(retries[0][0])
        output = ReviewResult(
            risks=[
                RiskFinding(
                    clause_id=first.clauses[0].id,
                    risk_type="payment",
                    risk_level="low",
                    evidence=first.clauses[0].original_text,
                    reason="测试风险",
                    recommendation="测试建议",
                )
            ]
        )
        reviewer = SimpleNamespace(
            review=AsyncMock(return_value=ReviewGraphResult(output))
        )

        async def execute():
            async with factory() as session:
                pipeline = DocumentIntelligencePipeline(
                    session,
                    SimpleNamespace(
                        parse=AsyncMock(
                            side_effect=AssertionError("Facts cache must be reused")
                        )
                    ),
                    FakeDocumentCapabilities(),
                )
                await run_contract_review(session, pipeline, reviewer, run_id)

        await asyncio.gather(execute(), execute())
        assert reviewer.review.await_count == 1
        async with factory() as session:
            run = await session.get(AnalysisRunModel, run_id)
            assert run.status == "completed" and run.review_version == "v2"
            assert (
                await session.scalar(
                    select(func.count()).select_from(ContractClauseModel)
                )
                == 0
            )
            risk_ids = list((await session.scalars(select(ContractRiskModel.id))).all())
            assert len(risk_ids) == 1

        async def publish_review():
            async with factory() as session, session.begin():
                await contract_db.complete_run(
                    session,
                    ReviewContext(run_id, version_id, "unused", "test.pdf"),
                    output,
                )

        await asyncio.gather(publish_review(), publish_review())
        async with factory() as session:
            assert (
                list((await session.scalars(select(ContractRiskModel.id))).all())
                == risk_ids
            )
            assert await contract_db.get_document_facts(session, version_id) == first
        # A late failure must wait for publication, not hold Run while waiting for Version.
        raced_run_id = UUID((await retry())[0])
        async with factory() as session, session.begin():
            raced_run = await session.get(AnalysisRunModel, raced_run_id)
            raced_run.status = "analyzing"
            # Synthetic source rows: test real reference issuance and lock ordering,
            # not embedding/model quality (covered by the separate live script).
            from products.contract.models import (
                ContractKnowledgeDocumentModel,
                ContractKnowledgeChunkModel,
            )
            from products.contract.retrieval import reference_snapshot

            document = ContractKnowledgeDocumentModel(
                user_id=1,
                filename="reference.docx",
                source_key="unused",
                content_hash="f" * 64,
                byte_count=1,
                status="ready",
                embedding_model="test",
                chunk_count=1,
            )
            session.add(document)
            await session.flush()
            chunk = ContractKnowledgeChunkModel(
                id=uuid4(),
                document_id=document.id,
                user_id=1,
                document_version=1,
                generation=1,
                sequence=1,
                chunk_text="真实企业参考规范",
                locator={},
                token_index=["规范"],
                embedding=[1.0] + [0.0] * 1023,
                embedding_model="test",
            )
            session.add(chunk)
            await session.flush()
            reference = reference_snapshot(chunk, document)
            clause_ids = [str(first.clauses[0].id)]
        version_locked, failure_attempted = asyncio.Event(), asyncio.Event()

        async def successful_publication():
            async with factory() as session, session.begin():
                await session.scalar(
                    select(ContractVersionModel)
                    .where(ContractVersionModel.id == version_id)
                    .with_for_update()
                )
                version_locked.set()
                await failure_attempted.wait()
                await contract_db.record_review_references(
                    session,
                    ReviewContext(
                        raced_run_id, version_id, "unused", "test.pdf", user_id=1
                    ),
                    [reference],
                    clause_ids,
                )
                await contract_db.complete_run(
                    session,
                    ReviewContext(raced_run_id, version_id, "unused", "test.pdf"),
                    output,
                )

        async def late_failure():
            await version_locked.wait()
            async with factory() as session, session.begin():
                failure_attempted.set()
                await contract_db.fail_run(
                    session,
                    raced_run_id,
                    "late duplicate failure",
                    review_trace={"prompt_version": "must-not-overwrite"},
                )

        await asyncio.wait_for(
            asyncio.gather(successful_publication(), late_failure()), timeout=10
        )
        async with factory() as session:
            assert (
                await session.get(AnalysisRunModel, raced_run_id)
            ).status == "completed"
            snapshot = (
                await session.get(AnalysisRunModel, raced_run_id)
            ).context_snapshot
            assert snapshot["references"][0]["chunk_id"] == reference["chunk_id"]
            assert "review_trace" not in snapshot
            assert (
                await session.get(ContractVersionModel, version_id)
            ).status == "completed"
            assert await contract_db.get_document_facts(session, version_id) == first

        async def replay_publication():
            async with factory() as session, session.begin():
                context = ReviewContext(
                    raced_run_id, version_id, "unused", "test.pdf", user_id=1
                )
                await contract_db.record_review_references(
                    session, context, [reference], clause_ids
                )
                await contract_db.complete_run(session, context, output)

        await asyncio.wait_for(
            asyncio.gather(replay_publication(), replay_publication()), timeout=10
        )
        async with factory() as session:
            assert (
                await session.get(AnalysisRunModel, raced_run_id)
            ).context_snapshot == snapshot
        print(
            "PostgreSQL Review V2 concurrent retries/claims/publications/late failure: passed",
            flush=True,
        )
    finally:
        await engine.dispose()


def main():
    database_name = f"contract_facts_test_{uuid4().hex[:12]}"
    print(f"Creating disposable database {database_name}", flush=True)
    with psycopg.connect(
        _psycopg_url(POSTGRES_DATABASE), autocommit=True, connect_timeout=5
    ) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    engine = create_engine(_url(database_name), connect_args={"connect_timeout": 5})
    try:
        User.__table__.create(engine)
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option(
            "sqlalchemy.url", _url(database_name).render_as_string(hide_password=False)
        )
        command.upgrade(config, "head")
        asyncio.run(verify(database_name))
    finally:
        engine.dispose()
        with psycopg.connect(
            _psycopg_url(POSTGRES_DATABASE), autocommit=True, connect_timeout=5
        ) as admin:
            _drop_database(admin, database_name)
        print(f"Removed disposable database {database_name}", flush=True)


if __name__ == "__main__":
    main()
