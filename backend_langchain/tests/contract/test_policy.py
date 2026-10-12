import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from common.auth.dependencies import require_user
from common.database import get_db
from products.contract import db
from products.contract.api import router
from products.contract.domain.document import CanonicalContractClause
from products.contract.domain.review import ReviewContext
from products.contract.models import AnalysisRunModel
from products.contract.schemas.analysis import ReviewResult, validate_findings


def test_policy_crud_scope_snapshot_and_permissions(document_db):
    factory, version_id = document_db
    app = FastAPI()
    app.include_router(router)
    caller = [1]
    app.dependency_overrides[require_user] = lambda: SimpleNamespace(user_id=caller[0])

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = sessions

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            body = dict(
                name="企业采购期限",
                requirement="付款期限原则上不超过45天",
                severity="medium",
                applicable_party_role="buyer",
                applicable_contract_types=["procurement"],
            )
            created = await client.post("/api/contract-policies", json=body)
            assert created.status_code == 200
            policy = created.json()["data"]
            assert policy["version"] == 1
            pid = policy["id"]
            caller[0] = 999
            assert (await client.get("/api/contract-policies")).json()["data"][
                "policies"
            ] == []
            assert (
                await client.patch(
                    f"/api/contract-policies/{pid}",
                    json={"enabled": False, "expected_version": 1},
                )
            ).status_code == 404
            assert (
                await client.delete(f"/api/contract-policies/{pid}?expected_version=1")
            ).status_code == 404
            caller[0] = 1
            async with factory() as session, session.begin():
                runs = [
                    AnalysisRunModel(
                        version_id=version_id, status="completed", attempt=i + 1
                    )
                    for i in range(4)
                ]
                session.add_all(runs)
                await session.flush()
                for run, role, kind, expected in zip(
                    runs,
                    ["buyer", "supplier", "", "buyer"],
                    ["procurement", "procurement", "", "sales"],
                    [1, 0, 0, 0],
                ):
                    context = ReviewContext(
                        run.id,
                        version_id,
                        "key",
                        "test.docx",
                        user_id=1,
                        party_role=role,
                        contract_type=kind,
                    )
                    snapshot = await db.prepare_review_context(session, context)
                    assert len(snapshot["policies"]) == expected
                old_id, old_snapshot = runs[0].id, runs[0].context_snapshot
                with pytest.raises(ValueError):
                    await db.prepare_review_context(
                        session,
                        ReviewContext(
                            runs[1].id, version_id, "key", "test.docx", user_id=999
                        ),
                    )
            updated = await client.patch(
                f"/api/contract-policies/{pid}",
                json={"requirement": "付款期限不超过30天", "expected_version": 1},
            )
            assert updated.json()["data"]["version"] == 2
            assert (
                await client.patch(
                    f"/api/contract-policies/{pid}",
                    json={"enabled": False, "expected_version": 1},
                )
            ).status_code == 409
            disabled = await client.patch(
                f"/api/contract-policies/{pid}",
                json={"enabled": False, "expected_version": 2},
            )
            assert disabled.json()["data"]["version"] == 3
            archived = await client.delete(
                f"/api/contract-policies/{pid}?expected_version=3"
            )
            assert (
                archived.json()["data"]["archived"]
                and archived.json()["data"]["version"] == 4
            )
            assert (await client.get("/api/contract-policies")).json()["data"][
                "policies"
            ] == []
            async with factory() as session, session.begin():
                assert (
                    await session.get(AnalysisRunModel, old_id)
                ).context_snapshot == old_snapshot
                assert old_snapshot["policies"][0]["requirement"] == body["requirement"]
                new_run = AnalysisRunModel(
                    version_id=version_id, status="completed", attempt=5
                )
                session.add(new_run)
                await session.flush()
                assert (
                    await db.prepare_review_context(
                        session,
                        ReviewContext(
                            new_run.id,
                            version_id,
                            "key",
                            "test.docx",
                            user_id=1,
                            party_role="buyer",
                            contract_type="procurement",
                        ),
                    )
                )["policies"] == []
            assert (
                await client.post(
                    "/api/contract-policies", json=body | {"requirement": "  "}
                )
            ).status_code == 422
            assert (
                await client.post(
                    "/api/contract-policies", json=body | {"owner_id": 999}
                )
            ).status_code == 422

    asyncio.run(check())


def test_agent_uses_real_policy_ids_and_rejects_fabrication():
    from products.contract.agents.review import ReviewAgent, ReviewLimits

    version_id, clause_id, policy_id = uuid4(), uuid4(), uuid4()
    clause = CanonicalContractClause(
        clause_id, version_id, 1, "付款", "payment", "付款期限90天。", (uuid4(),)
    )
    policy = dict(
        id=str(policy_id),
        version=1,
        name="企业期限",
        requirement="不超过45天",
        severity="medium",
        category="payment",
    )
    risk = dict(
        clause_id=str(clause_id),
        risk_type="payment",
        risk_level="medium",
        evidence="付款期限90天。",
        reason="超过企业上限",
        recommendation="调整为45天内",
        policy_ids=[str(policy_id)],
    )
    invoke = AsyncMock(return_value={"risks": [risk]})
    model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(ainvoke=invoke)
    )
    result = asyncio.run(
        ReviewAgent(model, limits=ReviewLimits(react_enabled=False)).review(
            (clause,), metadata={}, policies=[policy]
        )
    )
    assert result.risks[0].policy_ids == [policy_id]
    assert str(policy_id) in invoke.call_args.args[0][1].content
    with pytest.raises(ValueError):
        validate_findings(result, (clause,), version_id)
    with pytest.raises(ValueError):
        validate_findings(
            ReviewResult.model_validate({"risks": [risk | {"risk_level": "low"}]}),
            (clause,),
            version_id,
            policies=[policy],
        )
    with pytest.raises(ValueError):
        validate_findings(
            ReviewResult.model_validate(
                {"risks": [risk | {"policy_ids": [str(uuid4())]}]}
            ),
            (clause,),
            version_id,
            policies=[policy],
        )
