from uuid import UUID
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException
from sqlalchemy import select
from app.db import get_db
from app.deps import require_user
from app.response import ok
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.document.contract_parser import MAX_BYTES
from infrastructure.document.contract_jobs import owned_version, upload_version, new_run, execute_analysis

router = APIRouter(prefix='/api/contracts', tags=['contract-analysis'])


@router.post('/{contract_id}/versions/upload')
async def upload(contract_id: UUID, background: BackgroundTasks, file: UploadFile = File(...),
                 user=Depends(require_user), db=Depends(get_db)):
    try:
        data = await file.read(MAX_BYTES + 1)
        version, run = await upload_version(db, user.user_id, contract_id, (file.filename or 'contract').replace('\\', '/').split('/')[-1], data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()
    background.add_task(execute_analysis, run.id)
    return ok('上传成功，开始分析', {'version_id': str(version.id), 'run_id': str(run.id)})


@router.post('/{contract_id}/versions/{version_id}/analyze')
async def analyze(contract_id: UUID, version_id: UUID, background: BackgroundTasks,
                  user=Depends(require_user), db=Depends(get_db)):
    version = await owned_version(db, user.user_id, contract_id, version_id)
    expected_key = f'contracts/{user.user_id}/{contract_id}/{version_id}/original.'
    if version.source_key not in (expected_key + 'pdf', expected_key + 'docx'):
        raise HTTPException(422, '请通过文件上传创建版本后再分析')
    run, created = await new_run(db, version)
    if created:
        background.add_task(execute_analysis, run.id)
    return ok('分析任务已提交', {'run_id': str(run.id)})


@router.get('/{contract_id}/versions/{version_id}/analysis')
async def analysis(contract_id: UUID, version_id: UUID, user=Depends(require_user), db=Depends(get_db)):
    await owned_version(db, user.user_id, contract_id, version_id)
    run = await db.scalar(select(AnalysisRunModel).where(AnalysisRunModel.version_id == version_id)
        .order_by(AnalysisRunModel.created_at.desc()).limit(1))
    return ok('获取分析成功', None if run is None else {
        'id': str(run.id), 'status': run.status, 'document_text': run.document_text,
        'result': run.result, 'error': run.error})
