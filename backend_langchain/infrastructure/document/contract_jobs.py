"""Demo execution adapter. Replace with a durable worker for production."""
import asyncio
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, func
from fastapi import HTTPException
from app.db import SessionLocal
from app.services.oss_client import put_object_bytes, download_to_path, delete_object
from infrastructure.db.models import ContractModel, ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.document.contract_parser import validate_file, parse_contract
from products.contract.agents.review_agent import analyze_text
from products.contract.application.analysis import review_document
from pathlib import Path
import tempfile
from pydantic import ValidationError


async def owned_version(db, user_id, contract_id, version_id):
    version = await db.scalar(select(ContractVersionModel).join(ContractModel).where(
        ContractModel.user_id == user_id, ContractModel.id == contract_id,
        ContractVersionModel.id == version_id))
    if version is None:
        raise HTTPException(404, '合同版本不存在')
    return version


async def upload_version(db, user_id, contract_id, filename, data):
    kind = validate_file(filename, data)
    contract = await db.scalar(select(ContractModel).where(
        ContractModel.id == contract_id, ContractModel.user_id == user_id).with_for_update())
    if contract is None:
        raise HTTPException(404, '合同不存在')
    version_id = uuid4()
    key = f'contracts/{user_id}/{contract_id}/{version_id}/original.{kind}'
    await asyncio.to_thread(put_object_bytes, key, data, content_type=(
        'application/pdf' if kind == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
    try:
        number = (await db.scalar(select(func.max(ContractVersionModel.number)).where(
            ContractVersionModel.contract_id == contract_id)) or 0) + 1
        version = ContractVersionModel(id=version_id, contract_id=contract_id, number=number,
            source_key=key, filename=filename, status='uploaded')
        db.add(version)
        await db.flush()
        run = AnalysisRunModel(version_id=version_id, status='pending')
        db.add(run)
        await db.commit()
        return version, run
    except Exception:
        await db.rollback()
        await asyncio.to_thread(delete_object, key)
        raise


async def new_run(db, version):
    # Serialize retries for the same version; reuse an in-flight run.
    await db.execute(select(ContractVersionModel).where(ContractVersionModel.id == version.id).with_for_update())
    active = await db.scalar(select(AnalysisRunModel).where(AnalysisRunModel.version_id == version.id,
        AnalysisRunModel.status.in_(['pending', 'parsing', 'analyzing'])))
    if active:
        return active, False
    run = AnalysisRunModel(version_id=version.id, status='pending')
    db.add(run)
    await db.commit()
    return run, True


async def execute_analysis(run_id):
    async with SessionLocal() as db:
        run = await db.get(AnalysisRunModel, run_id)
        if run is None or run.status != 'pending':
            return
        try:
            run.status = 'parsing'
            await db.commit()
            version = await db.get(ContractVersionModel, run.version_id)
            def extract():
                with tempfile.TemporaryDirectory(prefix='contract-') as temp:
                    path = Path(temp) / 'original'
                    download_to_path(version.source_key, path)
                    return parse_contract(version.filename, path.read_bytes())
            run.document_text = await asyncio.to_thread(extract)
            run.status = 'analyzing'
            await db.commit()
            result = await asyncio.wait_for(review_document(run.document_text, analyze_text), timeout=240)
            run.result = result.model_dump()
            run.status = 'completed'
        except Exception as exc:
            run.status = 'failed'
            run.error = (
                'AI 返回格式不符合要求，请重新分析'
                if isinstance(exc, ValidationError)
                else str(exc) if isinstance(exc, ValueError)
                else '分析服务暂不可用或超时，请稍后重新分析'
            )
        run.finished_at = datetime.utcnow()
        await db.commit()
