from uuid import UUID
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, HTTPException
from app.db import get_db
from app.deps import require_user
from app.dependencies.contract import get_contract_review_service
from app.response import ok
from infrastructure.document.contract_parser import MAX_BYTES
from infrastructure.document.contract_jobs import owned_version, upload_version, new_run, execute_analysis
from products.contract.application.review_service import ContractReviewApplicationService
from products.contract.domain.review import ReviewRunRecord, ReviewSnapshot

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
async def analysis(
    contract_id: UUID,
    version_id: UUID,
    user=Depends(require_user),
    service: ContractReviewApplicationService = Depends(get_contract_review_service),
):
    try:
        snapshot = await service.get(
            user_id=user.user_id,
            contract_id=contract_id,
            version_id=version_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return ok('获取分析成功', _snapshot_payload(snapshot))


@router.get('/{contract_id}/versions/{version_id}/analysis-runs')
async def analysis_runs(
    contract_id: UUID,
    version_id: UUID,
    user=Depends(require_user),
    service: ContractReviewApplicationService = Depends(get_contract_review_service),
):
    try:
        snapshot = await service.get(
            user_id=user.user_id,
            contract_id=contract_id,
            version_id=version_id,
        )
        runs = await service.history(
            user_id=user.user_id,
            contract_id=contract_id,
            version_id=version_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    selected_id = snapshot.selected_run.id if snapshot.selected_run else None
    return ok(
        '获取分析历史成功',
        {
            'selected_run_id': str(selected_id) if selected_id else None,
            'runs': [
                {**_run_payload(run), 'selected': run.id == selected_id}
                for run in runs
            ],
        },
    )


@router.post('/{contract_id}/versions/{version_id}/analysis-runs/{run_id}/select')
async def select_analysis_run(
    contract_id: UUID,
    version_id: UUID,
    run_id: UUID,
    user=Depends(require_user),
    service: ContractReviewApplicationService = Depends(get_contract_review_service),
):
    try:
        snapshot = await service.select(
            user_id=user.user_id,
            contract_id=contract_id,
            version_id=version_id,
            run_id=run_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return ok('已切换到所选分析记录', _snapshot_payload(snapshot))


def _run_payload(run: ReviewRunRecord) -> dict:
    return {
        'id': str(run.id),
        'status': run.status,
        'current_step': run.current_step,
        'attempt': run.attempt,
        'error': run.error,
        'model_name': run.model_name,
        'prompt_version': run.prompt_version,
        'created_at': run.created_at.isoformat() if run.created_at else None,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
    }


def _snapshot_payload(snapshot: ReviewSnapshot) -> dict | None:
    latest = snapshot.latest_run
    selected = snapshot.selected_run
    if latest is None and selected is None:
        return None
    visible = selected or latest
    return {
        'id': str(latest.id) if latest else str(visible.id),
        'status': latest.status if latest else visible.status,
        'current_step': latest.current_step if latest else visible.current_step,
        'attempt': latest.attempt if latest else visible.attempt,
        'document_text': snapshot.document_text,
        'result': visible.result,
        'error': latest.error if latest else visible.error,
        'latest_run_id': str(latest.id) if latest else None,
        'selected_run_id': str(selected.id) if selected else None,
        'is_showing_previous': bool(latest and selected and latest.id != selected.id),
        'clauses': [
            {
                'id': str(clause.id),
                'sequence': clause.sequence,
                'clause_type': clause.clause_type,
                'title': clause.title,
                'original_text': clause.original_text,
                'summary': clause.summary,
                'locator': clause.locator,
            }
            for clause in snapshot.clauses
        ],
        'risks': [
            {
                'id': str(risk.id),
                'clause_id': str(risk.clause_id) if risk.clause_id else None,
                'title': risk.title,
                'risk_level': risk.risk_level,
                'evidence_text': risk.evidence_text,
                'reason': risk.reason,
                'suggestion': risk.suggestion,
                'review_status': risk.review_status,
                'reviewer_note': risk.reviewer_note,
            }
            for risk in snapshot.risks
        ],
    }
