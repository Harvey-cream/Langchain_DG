from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.auth.dependencies import require_user
from common.account.models import User
from common.http import fail, ok
from products.contract import db as contract_db
from products.contract.models import (
    AnalysisRunModel,
    ContractModel,
    ContractVersionModel,
    CustomerModel,
)
from products.contract.document.contract_jobs import execute_analysis
from products.contract.document.contract_parser import MAX_BYTES, validate_file
from common.storage.adapter import OssObjectStorage
from products.contract.domain.review import ReviewRunRecord, ReviewSnapshot
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
):
    storage = OssObjectStorage()
    try:
        data = await file.read(MAX_BYTES + 1)
        safe_filename = (file.filename or "contract").replace("\\", "/").split("/")[-1]
        kind = validate_file(safe_filename, data)

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
                    prompt_version="v2",
                )
                db.add_all([version, run])
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
                prompt_version="v2",
            )
            version.status = "pending"
            db.add(run)
            await db.flush()
            created = True

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
    runs = await contract_db.list_history(
        db, user.user_id, contract_id, version_id
    )
    if runs is None:
        raise HTTPException(404, "合同版本不存在")

    selected_id = snapshot.selected_run.id if snapshot.selected_run else None
    return ok(
        "获取分析历史成功",
        {
            "selected_run_id": str(selected_id) if selected_id else None,
            "runs": [
                {**_run_payload(run), "selected": run.id == selected_id}
                for run in runs
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
        "error": latest.error if latest else visible.error,
        "latest_run_id": str(latest.id) if latest else None,
        "selected_run_id": str(selected.id) if selected else None,
        "is_showing_previous": bool(latest and selected and latest.id != selected.id),
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
                "evidence_text": risk.evidence_text,
                "reason": risk.reason,
                "suggestion": risk.suggestion,
                "review_status": risk.review_status,
                "reviewer_note": risk.reviewer_note,
            }
            for risk in snapshot.risks
        ],
    }
