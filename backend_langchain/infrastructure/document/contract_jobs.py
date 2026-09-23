"""Demo execution adapter. Replace with a durable worker for production."""

import asyncio
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select

from app.db import SessionLocal
from app.services.oss_client import delete_object, put_object_bytes
from infrastructure.db.models import ContractModel, ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.db.repositories.contract_review import SqlAlchemyContractReviewRepository
from infrastructure.document.contract_parser import validate_file
from infrastructure.document.contract_source import OssContractDocumentParser
from products.contract.agents.review_agent import LangChainContractReviewer
from products.contract.workflows.review_workflow import ContractReviewWorkflow

ACTIVE_STATUSES = ("pending", "parsing", "analyzing")


async def owned_version(db, user_id, contract_id, version_id):
    version = await db.scalar(
        select(ContractVersionModel)
        .join(ContractModel)
        .where(
            ContractModel.user_id == user_id,
            ContractModel.id == contract_id,
            ContractVersionModel.id == version_id,
        )
    )
    if version is None:
        raise HTTPException(404, "合同版本不存在")
    return version


async def upload_version(db, user_id, contract_id, filename, data):
    kind = validate_file(filename, data)
    contract = await db.scalar(
        select(ContractModel)
        .where(ContractModel.id == contract_id, ContractModel.user_id == user_id)
        .with_for_update()
    )
    if contract is None:
        raise HTTPException(404, "合同不存在")
    version_id = uuid4()
    key = f"contracts/{user_id}/{contract_id}/{version_id}/original.{kind}"
    content_type = (
        "application/pdf"
        if kind == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    await asyncio.to_thread(put_object_bytes, key, data, content_type=content_type)
    try:
        number = (
            await db.scalar(
                select(func.max(ContractVersionModel.number)).where(
                    ContractVersionModel.contract_id == contract_id
                )
            )
            or 0
        ) + 1
        version = ContractVersionModel(
            id=version_id,
            contract_id=contract_id,
            number=number,
            source_key=key,
            filename=filename,
            status="pending",
        )
        db.add(version)
        await db.flush()
        run = AnalysisRunModel(
            version_id=version_id,
            status="pending",
            current_step="queued",
            attempt=1,
            prompt_version="v2",
        )
        db.add(run)
        await db.commit()
        return version, run
    except Exception:
        await db.rollback()
        await asyncio.to_thread(delete_object, key)
        raise


async def new_run(db, version):
    # Serialize retries for the same version; reuse an in-flight run.
    await db.execute(
        select(ContractVersionModel)
        .where(ContractVersionModel.id == version.id)
        .with_for_update()
    )
    active = await db.scalar(
        select(AnalysisRunModel).where(
            AnalysisRunModel.version_id == version.id,
            AnalysisRunModel.status.in_(ACTIVE_STATUSES),
        )
    )
    if active:
        return active, False
    attempt = (
        await db.scalar(
            select(func.max(AnalysisRunModel.attempt)).where(
                AnalysisRunModel.version_id == version.id
            )
        )
        or 0
    ) + 1
    run = AnalysisRunModel(
        version_id=version.id,
        status="pending",
        current_step="queued",
        attempt=attempt,
        prompt_version="v2",
    )
    db.add(run)
    version.status = "pending"
    await db.commit()
    return run, True


async def execute_analysis(run_id: UUID) -> None:
    async with SessionLocal() as db:
        workflow = ContractReviewWorkflow(
            SqlAlchemyContractReviewRepository(db),
            OssContractDocumentParser(),
            LangChainContractReviewer(),
        )
        await workflow.run(run_id)
