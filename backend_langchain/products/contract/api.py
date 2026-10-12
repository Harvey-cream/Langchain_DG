from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.auth.dependencies import require_user
from common.account.models import User
from common.http import fail, ok
from products.contract import db as contract_db
from products.contract.models import (
    AnalysisRunModel,
    ContractModel,
    ContractPolicyModel,
    ContractKnowledgeDocumentModel,
    ContractKnowledgeChunkModel,
    ContractVersionModel,
    CustomerModel,
)
from products.contract.document.contract_jobs import execute_analysis
from products.contract.document.contract_parser import MAX_BYTES, validate_file
from common.storage.adapter import OssObjectStorage
from products.contract.domain.review import (
    ReviewRunRecord,
    ReviewSnapshot,
    REVIEW_PROMPT_VERSION,
)
from products.contract.schemas.api import (
    ReviewRequest,
    PolicyWrite,
    PolicyUpdate,
    KnowledgeDocumentUpdate,
    KnowledgeSearch,
)
from products.contract.knowledge import ingest_document, finish_document_delete
from products.contract.schemas import (
    ContractCreate,
    ContractResponse,
    ContractVersionCreate,
    ContractVersionResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter(prefix="/api")
ACTIVE_RUN_STATUSES = ("pending", "parsing", "analyzing")


def _contract_response(item) -> dict:
    return ContractResponse.model_validate(item).model_dump(mode="json")


def _version_response(item) -> dict:
    return ContractVersionResponse.model_validate(item).model_dump(mode="json")


def _customer_response(customer) -> dict:
    return CustomerResponse.model_validate(customer).model_dump(mode="json")


# Contract and version endpoints.
@router.post("/contracts", tags=["contracts"])
async def create_contract(
    body: ContractCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    title = body.title.strip()
    if not title:
        return fail("contract title is required", status_code=400)

    async with db.begin():
        customer = await db.scalar(
            select(CustomerModel).where(
                CustomerModel.id == body.customer_id,
                CustomerModel.user_id == user.user_id,
            )
        )
        if customer is None:
            return fail("customer not found", status_code=404)

        contract = ContractModel(
            id=uuid4(),
            user_id=user.user_id,
            customer_id=body.customer_id,
            title=title,
        )
        db.add(contract)
        await db.flush()

    return ok("合同创建成功", _contract_response(contract))


@router.get("/contracts", tags=["contracts"])
async def list_contracts(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    contracts = (
        await db.scalars(
            select(ContractModel)
            .where(ContractModel.user_id == user.user_id)
            .order_by(ContractModel.created_at)
        )
    ).all()
    return ok(
        "获取合同成功",
        {"contracts": [_contract_response(item) for item in contracts]},
    )


@router.get("/contracts/{contract_id}", tags=["contracts"])
async def get_contract(
    contract_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await db.scalar(
        select(ContractModel).where(
            ContractModel.id == contract_id,
            ContractModel.user_id == user.user_id,
        )
    )
    if contract is None:
        return fail("contract not found", status_code=404)
    return ok("获取合同成功", _contract_response(contract))


@router.post("/contracts/{contract_id}/versions", tags=["contracts"])
async def create_contract_version(
    contract_id: UUID,
    body: ContractVersionCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    source_key = body.source_key.strip()
    filename = body.filename.strip()
    if not source_key:
        return fail("version source key is required", status_code=400)
    if not filename:
        return fail("version filename is required", status_code=400)

    async with db.begin():
        # 同一合同的版本号必须在行锁内分配，避免并发创建出重复版本号。
        contract = await db.scalar(
            select(ContractModel)
            .where(
                ContractModel.id == contract_id,
                ContractModel.user_id == user.user_id,
            )
            .with_for_update()
        )
        if contract is None:
            return fail("contract not found", status_code=404)

        current = await db.scalar(
            select(func.max(ContractVersionModel.number)).where(
                ContractVersionModel.contract_id == contract_id
            )
        )
        version = ContractVersionModel(
            id=uuid4(),
            contract_id=contract_id,
            number=int(current or 0) + 1,
            source_key=source_key,
            filename=filename,
            status="created",
        )
        db.add(version)
        await db.flush()

    return ok("合同版本创建成功", _version_response(version))


@router.get("/contracts/{contract_id}/versions", tags=["contracts"])
async def list_contract_versions(
    contract_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await db.scalar(
        select(ContractModel.id).where(
            ContractModel.id == contract_id,
            ContractModel.user_id == user.user_id,
        )
    )
    if contract is None:
        return fail("contract not found", status_code=404)

    versions = (
        await db.scalars(
            select(ContractVersionModel)
            .where(ContractVersionModel.contract_id == contract_id)
            .order_by(ContractVersionModel.number)
        )
    ).all()
    return ok(
        "获取合同版本成功",
        {"versions": [_version_response(item) for item in versions]},
    )


@router.get("/contracts/{contract_id}/versions/{version_id}", tags=["contracts"])
async def get_contract_version(
    contract_id: UUID,
    version_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    version = await db.scalar(
        select(ContractVersionModel)
        .join(ContractModel, ContractModel.id == ContractVersionModel.contract_id)
        .where(
            ContractModel.id == contract_id,
            ContractModel.user_id == user.user_id,
            ContractVersionModel.id == version_id,
        )
    )
    if version is None:
        return fail("contract version not found", status_code=404)
    return ok("获取合同版本成功", _version_response(version))


# Contract customer endpoints.
@router.post("/customers", tags=["contract-customers"])
async def create_customer(
    body: CustomerCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    name = body.name.strip()
    email = body.email.strip()
    if not name:
        return fail("customer name is required", status_code=400)
    if not email or "@" not in email:
        return fail("valid customer email is required", status_code=400)

    async with db.begin():
        customer = CustomerModel(user_id=user.user_id, name=name, email=email)
        db.add(customer)
        await db.flush()

    return ok("客户创建成功", _customer_response(customer))


@router.get("/customers", tags=["contract-customers"])
async def list_customers(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    customers = (
        await db.scalars(
            select(CustomerModel)
            .where(CustomerModel.user_id == user.user_id)
            .order_by(CustomerModel.created_at)
        )
    ).all()
    return ok(
        "获取客户成功",
        {"customers": [_customer_response(item) for item in customers]},
    )


@router.get("/customers/{customer_id}", tags=["contract-customers"])
async def get_customer(
    customer_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    customer = await db.scalar(
        select(CustomerModel).where(
            CustomerModel.id == customer_id,
            CustomerModel.user_id == user.user_id,
        )
    )
    if customer is None:
        return fail("customer not found", status_code=404)
    return ok("获取客户成功", _customer_response(customer))


@router.patch("/customers/{customer_id}", tags=["contract-customers"])
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    name = body.name.strip()
    email = body.email.strip()
    if not name or "@" not in email:
        return fail("valid customer name and email are required", status_code=400)

    async with db.begin():
        customer = await db.scalar(
            select(CustomerModel)
            .where(
                CustomerModel.id == customer_id,
                CustomerModel.user_id == user.user_id,
            )
            .with_for_update()
        )
        if customer is None:
            return fail("customer not found", status_code=404)

        customer.name = name
        customer.email = email
        await db.flush()

    return ok("客户更新成功", _customer_response(customer))


@router.delete("/customers/{customer_id}", tags=["contract-customers"])
async def delete_customer(
    customer_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        customer = await db.scalar(
            select(CustomerModel).where(
                CustomerModel.id == customer_id,
                CustomerModel.user_id == user.user_id,
            )
        )
        if customer is None:
            return fail("customer not found", status_code=404)
        await db.delete(customer)

    return ok("客户删除成功")


# Version analysis endpoints.
@router.post("/contracts/{contract_id}/versions/upload", tags=["contract-analysis"])
async def upload(
    contract_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    our_party: str = Form(default="", max_length=255),
    party_role: str = Form(default="", max_length=64),
    contract_type: str = Form(default="", max_length=64),
):
    storage = OssObjectStorage()
    try:
        data = await file.read(MAX_BYTES + 1)
        safe_filename = (file.filename or "contract").replace("\\", "/").split("/")[-1]
        kind = validate_file(safe_filename, data)
        review_request = ReviewRequest(
            our_party=our_party if isinstance(our_party, str) else "",
            party_role=party_role if isinstance(party_role, str) else "",
            contract_type=contract_type if isinstance(contract_type, str) else "",
        )
        stance = review_request.our_party.strip()

        # 权限查询是短事务；上传 OSS 时不能持有数据库行锁。
        async with db.begin():
            owned_contract_id = await db.scalar(
                select(ContractModel.id).where(
                    ContractModel.id == contract_id,
                    ContractModel.user_id == user.user_id,
                )
            )
            if owned_contract_id is None:
                raise HTTPException(404, "合同不存在")

        version_id = uuid4()
        source_key = (
            f"contracts/{user.user_id}/{contract_id}/{version_id}/original.{kind}"
        )
        content_type = (
            "application/pdf"
            if kind == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        await asyncio.to_thread(
            storage.put,
            source_key,
            data,
            content_type=content_type,
        )

        try:
            async with db.begin():
                # OSS 上传期间合同可能被删除，写库前重新校验并加锁。
                contract = await db.scalar(
                    select(ContractModel)
                    .where(
                        ContractModel.id == contract_id,
                        ContractModel.user_id == user.user_id,
                    )
                    .with_for_update()
                )
                if contract is None:
                    raise HTTPException(404, "合同不存在")

                current = await db.scalar(
                    select(func.max(ContractVersionModel.number)).where(
                        ContractVersionModel.contract_id == contract_id
                    )
                )
                version = ContractVersionModel(
                    id=version_id,
                    contract_id=contract_id,
                    number=int(current or 0) + 1,
                    source_key=source_key,
                    filename=safe_filename,
                    status="pending",
                )
                run = AnalysisRunModel(
                    id=uuid4(),
                    version_id=version_id,
                    status="pending",
                    current_step="queued",
                    attempt=1,
                    prompt_version=REVIEW_PROMPT_VERSION,
                    review_version="v2",
                    our_party=stance,
                    party_role=review_request.party_role,
                    contract_type=review_request.contract_type,
                )
                # 未声明 ORM relationship，必须先写父版本，避免 Run 先 INSERT 触发外键错误。
                db.add(version)
                await db.flush()
                db.add(run)
                await db.flush()
        except Exception:
            await asyncio.to_thread(storage.delete, source_key)
            raise

        # 提交成功后再入后台任务，任务不会读到尚未提交的 Run。
        background_tasks.add_task(execute_analysis, run.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()

    return ok(
        "上传成功，开始分析",
        {"version_id": str(version.id), "run_id": str(run.id)},
    )


@router.post(
    "/contracts/{contract_id}/versions/{version_id}/analyze",
    tags=["contract-analysis"],
)
async def analyze(
    contract_id: UUID,
    version_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    body: ReviewRequest | None = None,
):
    created = False
    async with db.begin():
        version = await db.scalar(
            select(ContractVersionModel)
            .join(ContractModel, ContractModel.id == ContractVersionModel.contract_id)
            .where(
                ContractModel.id == contract_id,
                ContractModel.user_id == user.user_id,
                ContractVersionModel.id == version_id,
            )
            .with_for_update()
        )
        if version is None:
            raise HTTPException(404, "合同版本不存在")

        expected = f"contracts/{user.user_id}/{contract_id}/{version_id}/original."
        if version.source_key not in (expected + "pdf", expected + "docx"):
            raise HTTPException(422, "请通过文件上传创建版本后再分析")

        run = await db.scalar(
            select(AnalysisRunModel).where(
                AnalysisRunModel.version_id == version_id,
                AnalysisRunModel.status.in_(ACTIVE_RUN_STATUSES),
            )
        )
        if run is None:
            current = await db.scalar(
                select(func.max(AnalysisRunModel.attempt)).where(
                    AnalysisRunModel.version_id == version_id
                )
            )
            run = AnalysisRunModel(
                id=uuid4(),
                version_id=version_id,
                status="pending",
                current_step="queued",
                attempt=int(current or 0) + 1,
                prompt_version=REVIEW_PROMPT_VERSION,
                review_version="v2",
                our_party=body.our_party.strip() if body else "",
                party_role=body.party_role if body else "",
                contract_type=body.contract_type if body else "",
            )
            version.status = "pending"
            db.add(run)
            await db.flush()
            created = True
        elif body is not None and (
            run.our_party != body.our_party.strip()
            or run.party_role != body.party_role
            or run.contract_type != body.contract_type
        ):
            raise HTTPException(409, "已有审查正在执行，请完成后再变更我方身份")

    if created:
        background_tasks.add_task(execute_analysis, run.id)
    return ok("分析任务已提交", {"run_id": str(run.id)})


@router.get(
    "/contracts/{contract_id}/versions/{version_id}/analysis",
    tags=["contract-analysis"],
)
async def analysis(
    contract_id: UUID,
    version_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot = await contract_db.load_snapshot(
        db, user.user_id, contract_id, version_id
    )
    if snapshot is None:
        raise HTTPException(404, "合同版本不存在")
    return ok("获取分析成功", _snapshot_payload(snapshot))


@router.get(
    "/contracts/{contract_id}/versions/{version_id}/analysis-runs",
    tags=["contract-analysis"],
)
async def analysis_runs(
    contract_id: UUID,
    version_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    snapshot = await contract_db.load_snapshot(
        db, user.user_id, contract_id, version_id
    )
    if snapshot is None:
        raise HTTPException(404, "合同版本不存在")
    runs = await contract_db.list_history(db, user.user_id, contract_id, version_id)
    if runs is None:
        raise HTTPException(404, "合同版本不存在")

    selected_id = snapshot.selected_run.id if snapshot.selected_run else None
    return ok(
        "获取分析历史成功",
        {
            "selected_run_id": str(selected_id) if selected_id else None,
            "runs": [
                {**_run_payload(run), "selected": run.id == selected_id} for run in runs
            ],
        },
    )


@router.post(
    "/contracts/{contract_id}/versions/{version_id}/analysis-runs/{run_id}/select",
    tags=["contract-analysis"],
)
async def select_analysis_run(
    contract_id: UUID,
    version_id: UUID,
    run_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        selected = await contract_db.select_run(
            db, user.user_id, contract_id, version_id, run_id
        )
        if not selected:
            raise HTTPException(404, "可回退的成功分析记录不存在")

    snapshot = await contract_db.load_snapshot(
        db, user.user_id, contract_id, version_id
    )
    if snapshot is None:
        raise HTTPException(404, "合同版本不存在")
    return ok("已切换到所选分析记录", _snapshot_payload(snapshot))


def _run_payload(run: ReviewRunRecord) -> dict:
    return {
        "id": str(run.id),
        "status": run.status,
        "current_step": run.current_step,
        "attempt": run.attempt,
        "error": run.error,
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "review_version": run.review_version,
        "our_party": run.our_party,
        "party_role": run.party_role,
        "contract_type": run.contract_type,
        "quality_gate": run.context_snapshot.get("quality_gate"),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _snapshot_payload(snapshot: ReviewSnapshot) -> dict | None:
    latest = snapshot.latest_run
    selected = snapshot.selected_run
    if latest is None and selected is None:
        return None
    visible = selected or latest
    return {
        "id": str(latest.id) if latest else str(visible.id),
        "status": latest.status if latest else visible.status,
        "current_step": latest.current_step if latest else visible.current_step,
        "attempt": latest.attempt if latest else visible.attempt,
        "document_text": snapshot.document_text,
        "result": visible.result,
        "review_version": visible.review_version,
        "our_party": visible.our_party,
        "party_role": visible.party_role,
        "contract_type": visible.contract_type,
        "context_snapshot": visible.context_snapshot,
        "model_name": visible.model_name,
        "prompt_version": visible.prompt_version,
        "latest_quality_gate": (
            latest.context_snapshot.get("quality_gate") if latest else None
        ),
        "error": latest.error if latest else visible.error,
        "latest_run_id": str(latest.id) if latest else None,
        "selected_run_id": str(selected.id) if selected else None,
        "is_showing_previous": bool(latest and selected and latest.id != selected.id),
        "facts": (
            {
                "metadata": snapshot.facts.metadata,
                "parser_version": snapshot.facts.document.parser_version,
                "intelligence_version": snapshot.facts.intelligence_version,
                "coverage": {
                    "ratio": snapshot.facts.coverage.ratio,
                    "covered_blocks": snapshot.facts.coverage.covered_meaningful_blocks,
                    "total_blocks": snapshot.facts.coverage.total_meaningful_blocks,
                    "warnings": list(snapshot.facts.coverage.warnings),
                },
            }
            if snapshot.facts
            else None
        ),
        "canonical_clauses": (
            [
                {
                    "id": str(c.id),
                    "sequence": c.sequence,
                    "title": c.title,
                    "clause_type": c.clause_type,
                    "original_text": c.original_text,
                    "source_block_ids": [str(key) for key in c.source_block_ids],
                    "pages": list(c.pages),
                }
                for c in snapshot.facts.clauses
            ]
            if snapshot.facts
            else []
        ),
        "clauses": [
            {
                "id": str(clause.id),
                "sequence": clause.sequence,
                "clause_type": clause.clause_type,
                "title": clause.title,
                "original_text": clause.original_text,
                "summary": clause.summary,
                "locator": clause.locator,
            }
            for clause in snapshot.clauses
        ],
        "risks": [
            {
                "id": str(risk.id),
                "clause_id": str(risk.clause_id) if risk.clause_id else None,
                "title": risk.title,
                "risk_level": risk.risk_level,
                "risk_type": risk.risk_type,
                "evidence": risk.evidence_text,
                "recommendation": risk.suggestion,
                "related_clause_ids": [str(key) for key in risk.related_clause_ids],
                "policy_ids": [str(key) for key in risk.policy_ids],
                "reference_citations": list(risk.reference_citations),
                "evidence_text": risk.evidence_text,
                "reason": risk.reason,
                "suggestion": risk.suggestion,
                "review_status": risk.review_status,
                "reviewer_note": risk.reviewer_note,
            }
            for risk in snapshot.risks
        ],
    }


# User-owned Contract policies; history keeps a Run snapshot rather than mutable FKs.
def _policy_payload(policy: ContractPolicyModel) -> dict:
    return {
        **contract_db.policy_snapshot(policy),
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


@router.get("/contract-policies", tags=["contract-policy"])
async def list_policies(
    include_archived: bool = False,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ContractPolicyModel).where(
        ContractPolicyModel.user_id == user.user_id
    )
    if not include_archived:
        query = query.where(ContractPolicyModel.archived.is_(False))
    rows = (
        await db.scalars(
            query.order_by(
                ContractPolicyModel.created_at.desc(), ContractPolicyModel.id
            )
        )
    ).all()
    return ok("获取规则成功", {"policies": [_policy_payload(p) for p in rows]})


@router.post("/contract-policies", tags=["contract-policy"])
async def create_policy(
    body: PolicyWrite,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        policy = ContractPolicyModel(user_id=user.user_id, **body.model_dump())
        db.add(policy)
        await db.flush()
    return ok("规则已创建", _policy_payload(policy))


@router.patch("/contract-policies/{policy_id}", tags=["contract-policy"])
async def update_policy(
    policy_id: UUID,
    body: PolicyUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        policy = await db.scalar(
            select(ContractPolicyModel)
            .where(
                ContractPolicyModel.id == policy_id,
                ContractPolicyModel.user_id == user.user_id,
                ContractPolicyModel.archived.is_(False),
            )
            .with_for_update()
        )
        if policy is None:
            raise HTTPException(404, "规则不存在")
        if policy.version != body.expected_version:
            raise HTTPException(409, "规则已被修改，请刷新后重试")
        changes = body.model_dump(exclude_unset=True, exclude={"expected_version"})
        try:
            values = PolicyWrite.model_validate(
                {key: getattr(policy, key) for key in PolicyWrite.model_fields}
                | changes
            )
        except ValueError as exc:
            raise HTTPException(422, "规则字段不符合要求") from exc
        for key, value in values.model_dump().items():
            setattr(policy, key, value)
        policy.version += 1
        policy.updated_at = contract_db._now()
        await db.flush()
    return ok("规则已修改", _policy_payload(policy))


@router.delete("/contract-policies/{policy_id}", tags=["contract-policy"])
async def archive_policy(
    policy_id: UUID,
    expected_version: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        policy = await db.scalar(
            select(ContractPolicyModel)
            .where(
                ContractPolicyModel.id == policy_id,
                ContractPolicyModel.user_id == user.user_id,
            )
            .with_for_update()
        )
        if policy is None:
            raise HTTPException(404, "规则不存在")
        if not policy.archived:
            if policy.version != expected_version:
                raise HTTPException(409, "规则已被修改，请刷新后重试")
            policy.archived, policy.enabled = True, False
            policy.version += 1
            policy.updated_at = contract_db._now()
        await db.flush()
    return ok("规则已归档，历史引用保留", _policy_payload(policy))


# Private reference documents. HTTP CRUD remains beside these endpoints.
def _knowledge_payload(document: ContractKnowledgeDocumentModel) -> dict:
    fields = (
        "filename",
        "document_version",
        "category",
        "status",
        "generation",
        "attempt",
        "chunk_count",
        "byte_count",
        "page_count",
        "embedding_model",
        "error",
    )
    return {
        "id": str(document.id),
        **{key: getattr(document, key) for key in fields},
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


@router.get("/contract-knowledge/documents", tags=["contract-knowledge"])
async def list_knowledge_documents(
    user: User = Depends(require_user), db: AsyncSession = Depends(get_db)
):
    documents = (
        await db.scalars(
            select(ContractKnowledgeDocumentModel)
            .where(
                ContractKnowledgeDocumentModel.user_id == user.user_id,
                ContractKnowledgeDocumentModel.status != "deleted",
            )
            .order_by(
                ContractKnowledgeDocumentModel.created_at.desc(),
                ContractKnowledgeDocumentModel.id,
            )
        )
    ).all()
    return ok(
        "获取知识库成功", {"documents": [_knowledge_payload(d) for d in documents]}
    )


@router.post("/contract-knowledge/documents/upload", tags=["contract-knowledge"])
async def upload_knowledge_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(default="other", max_length=64),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    storage = OssObjectStorage()
    try:
        data = await file.read(MAX_BYTES + 1)
        filename = (file.filename or "reference").replace("\\", "/").split("/")[-1]
        if len(filename) > 512:
            raise HTTPException(422, "知识库文件名不能超过 512 个字符")
        try:
            kind = validate_file(filename, data)
            classification = KnowledgeDocumentUpdate(
                category=category, expected_generation=1
            ).category
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        digest, document_id = hashlib.sha256(data).hexdigest(), uuid4()
        duplicate = False
        # Persist a recoverable upload intent before OSS, never hold a lock across IO.
        try:
            async with db.begin():
                document = await db.scalar(
                    select(ContractKnowledgeDocumentModel)
                    .where(
                        ContractKnowledgeDocumentModel.user_id == user.user_id,
                        ContractKnowledgeDocumentModel.content_hash == digest,
                        ContractKnowledgeDocumentModel.status != "deleted",
                    )
                    .with_for_update()
                )
                if document is not None:
                    duplicate = True
                    if document.status in ("uploading", "deleting"):
                        raise HTTPException(409, "该文档正在上传或清理，请稍后重试")
                    if document.status != "failed":
                        return ok(
                            "相同原件已存在，未重复创建索引",
                            {
                                "document": _knowledge_payload(document),
                                "duplicate": True,
                            },
                        )
                    document.generation += 1
                    document.status, document.error = "uploading", None
                else:
                    document = ContractKnowledgeDocumentModel(
                        id=document_id,
                        user_id=user.user_id,
                        filename=filename,
                        source_key=f"contract-knowledge/{user.user_id}/{document_id}/v1/original.{kind}",
                        content_hash=digest,
                        category=classification,
                        status="uploading",
                        byte_count=len(data),
                    )
                    db.add(document)
                await db.flush()
                document_id, generation, key = (
                    document.id,
                    document.generation,
                    document.source_key,
                )
        except IntegrityError as exc:
            raise HTTPException(409, "相同文件正在上传，请刷新列表后重试") from exc
        try:
            await asyncio.to_thread(
                storage.put,
                key,
                data,
                content_type=(
                    "application/pdf"
                    if kind == "pdf"
                    else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
            )
        except Exception as exc:
            async with db.begin():
                document = await db.scalar(
                    select(ContractKnowledgeDocumentModel)
                    .where(ContractKnowledgeDocumentModel.id == document_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if document.status == "uploading" and document.generation == generation:
                    document.status, document.error = (
                        "failed",
                        "OSS 原件上传失败，请重新上传相同文件或删除文档",
                    )
            raise HTTPException(503, "原件上传失败，已保留可恢复记录") from exc
        async with db.begin():
            document = await db.scalar(
                select(ContractKnowledgeDocumentModel)
                .where(ContractKnowledgeDocumentModel.id == document_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            abandoned = (
                document.status != "uploading" or document.generation != generation
            )
            if not abandoned:
                document.status = "uploaded"
                await db.flush()
        if abandoned:
            # A concurrent delete may finish before this PUT. Clean that late object too.
            try:
                await asyncio.to_thread(storage.delete, key)
            except Exception:
                async with db.begin():
                    document = await db.scalar(
                        select(ContractKnowledgeDocumentModel)
                        .where(ContractKnowledgeDocumentModel.id == document_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    if document.status in ("deleting", "deleted"):
                        document.status, document.error = (
                            "deleting",
                            "延迟上传原件清理失败，请重试删除",
                        )
            raise HTTPException(409, "文档已在上传期间删除，请刷新列表")
        background_tasks.add_task(ingest_document, document_id, generation)
        return ok(
            "原件已上传，开始建立私有索引",
            {"document": _knowledge_payload(document), "duplicate": duplicate},
        )
    finally:
        await file.close()


@router.get("/contract-knowledge/documents/{document_id}", tags=["contract-knowledge"])
async def knowledge_document_detail(
    document_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(ContractKnowledgeDocumentModel).where(
            ContractKnowledgeDocumentModel.id == document_id,
            ContractKnowledgeDocumentModel.user_id == user.user_id,
            ContractKnowledgeDocumentModel.status != "deleted",
        )
    )
    if document is None:
        raise HTTPException(404, "知识库文档不存在")
    return ok("获取文档成功", _knowledge_payload(document))


@router.patch(
    "/contract-knowledge/documents/{document_id}", tags=["contract-knowledge"]
)
async def update_knowledge_document(
    document_id: UUID,
    body: KnowledgeDocumentUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        document = await db.scalar(
            select(ContractKnowledgeDocumentModel)
            .where(
                ContractKnowledgeDocumentModel.id == document_id,
                ContractKnowledgeDocumentModel.user_id == user.user_id,
                ContractKnowledgeDocumentModel.status.not_in(("deleted", "deleting")),
            )
            .with_for_update()
        )
        if document is None:
            raise HTTPException(404, "知识库文档不存在")
        if document.generation != body.expected_generation:
            raise HTTPException(409, "文档处理状态已变化，请刷新后重试")
        document.category = body.category
        await db.flush()
    return ok("分类已更新", _knowledge_payload(document))


@router.post(
    "/contract-knowledge/documents/{document_id}/reindex", tags=["contract-knowledge"]
)
async def reindex_knowledge_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    scheduled = False
    async with db.begin():
        document = await db.scalar(
            select(ContractKnowledgeDocumentModel)
            .where(
                ContractKnowledgeDocumentModel.id == document_id,
                ContractKnowledgeDocumentModel.user_id == user.user_id,
                ContractKnowledgeDocumentModel.status.not_in(("deleted", "deleting")),
            )
            .with_for_update()
        )
        if document is None:
            raise HTTPException(404, "知识库文档不存在")
        if document.status == "uploading":
            raise HTTPException(409, "请等待原件上传完成")
        if document.status not in ("uploaded", "processing"):
            document.generation += 1
            document.status, document.error, document.chunk_count = "uploaded", None, 0
            scheduled = True
        await db.flush()
        generation = document.generation
    if scheduled:
        background_tasks.add_task(ingest_document, document_id, generation)
    return ok("索引任务已提交", _knowledge_payload(document))


@router.delete(
    "/contract-knowledge/documents/{document_id}", tags=["contract-knowledge"]
)
async def delete_knowledge_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        document = await db.scalar(
            select(ContractKnowledgeDocumentModel)
            .where(
                ContractKnowledgeDocumentModel.id == document_id,
                ContractKnowledgeDocumentModel.user_id == user.user_id,
            )
            .with_for_update()
        )
        if document is None:
            raise HTTPException(404, "知识库文档不存在")
        if document.status == "deleted":
            return ok("文档已删除")
        if document.status != "deleting":
            document.generation += 1
        document.status, document.error, document.chunk_count = "deleting", None, 0
        await db.execute(
            delete(ContractKnowledgeChunkModel).where(
                ContractKnowledgeChunkModel.document_id == document_id,
                ContractKnowledgeChunkModel.user_id == user.user_id,
            )
        )
        generation = document.generation
    background_tasks.add_task(finish_document_delete, document_id, generation)
    return ok(
        "当前索引已撤下，原件正在清理；历史引用快照保留",
        {"id": str(document_id), "status": "deleting"},
    )


@router.get(
    "/contract-knowledge/documents/{document_id}/download", tags=["contract-knowledge"]
)
async def download_knowledge_document(
    document_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        document = await db.scalar(
            select(ContractKnowledgeDocumentModel).where(
                ContractKnowledgeDocumentModel.id == document_id,
                ContractKnowledgeDocumentModel.user_id == user.user_id,
                ContractKnowledgeDocumentModel.status.not_in(
                    ("deleted", "deleting", "uploading")
                ),
            )
        )
        if document is None:
            raise HTTPException(404, "知识库原件不存在")
        key, filename = document.source_key, document.filename

    def read():
        with tempfile.TemporaryDirectory(prefix="contract-reference-") as temp:
            path = Path(temp) / "original"
            OssObjectStorage().download(key, path)
            return path.read_bytes()

    try:
        data = await asyncio.to_thread(read)
    except Exception as exc:
        raise HTTPException(503, "原件暂时无法下载，请检查存储配置") from exc
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/contract-knowledge/chunks/{chunk_id}", tags=["contract-knowledge"])
async def knowledge_chunk_detail(
    chunk_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    from products.contract.retrieval import scoped_chunks, reference_snapshot

    row = (
        await db.execute(
            scoped_chunks(user.user_id).where(
                ContractKnowledgeChunkModel.id == chunk_id
            )
        )
    ).first()
    if row is None:
        raise HTTPException(404, "当前知识库片段不存在；历史引用请从历史审查查看")
    return ok("获取片段成功", reference_snapshot(*row))


@router.post("/contract-knowledge/search", tags=["contract-knowledge"])
async def search_knowledge(
    body: KnowledgeSearch,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from products.contract.retrieval import retrieve_references

    try:
        references = await retrieve_references(
            async_sessionmaker(db.bind, expire_on_commit=False),
            user.user_id,
            body.query,
        )
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    return ok("检索完成", {"references": references})


@router.get(
    "/contracts/{contract_id}/versions/{version_id}/analysis-runs/{run_id}/references/{chunk_id}",
    tags=["contract-analysis"],
)
async def historical_reference(
    contract_id: UUID,
    version_id: UUID,
    run_id: UUID,
    chunk_id: UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if (
        await contract_db._get_owned_version(db, user.user_id, contract_id, version_id)
        is None
    ):
        raise HTTPException(404, "合同版本不存在")
    run = await db.scalar(
        select(AnalysisRunModel).where(
            AnalysisRunModel.id == run_id, AnalysisRunModel.version_id == version_id
        )
    )
    reference = (
        next(
            (
                r
                for r in run.context_snapshot.get("references", [])
                if r["chunk_id"] == str(chunk_id)
            ),
            None,
        )
        if run
        else None
    )
    if reference is None:
        raise HTTPException(404, "历史引用不存在")
    return ok("获取审查时的引用快照成功", reference)
