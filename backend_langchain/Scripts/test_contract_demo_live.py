"""Explicit live smoke test with synthetic data; removes only its own fixtures."""
import asyncio
import secrets
from io import BytesIO
from uuid import UUID, uuid4
import httpx
from unittest.mock import AsyncMock, patch
from docx import Document
from sqlalchemy import delete, select
from app.main import app
from app.db import engine, SessionLocal, init_db_tables
from app.deps import require_user
from app.models import User
from infrastructure.db.models import CustomerModel, ContractModel, ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.document.contract_jobs import execute_analysis
from app.services.oss_client import delete_object


async def main():
    await init_db_tables()
    marker = uuid4().hex
    async with SessionLocal() as db:
        user = User(username='contract-demo-test', email=f'{marker}@example.invalid', password=secrets.token_hex(32))
        db.add(user); await db.commit()
        user_id = user.user_id
    app.dependency_overrides[require_user] = lambda: user
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', timeout=300) as client:
            customer = (await client.post('/api/customers', json={'name':'演示采购方', 'email':'buyer@example.invalid'})).json()['data']
            contract = (await client.post('/api/contracts', json={'title':'测试采购合同', 'customer_id':customer['id']})).json()['data']
            cid = contract['id']
            doc = Document()
            for paragraph in ['采购合同', '甲方：演示采购方。乙方：演示供应商。', '合同金额为人民币100000元，期限为一年。', '甲方应在签署当日支付全部价款。', '乙方可以随时终止合同且无需退款。', '甲方承担所有间接损失，赔偿金额不设上限。']:
                doc.add_paragraph(paragraph)
            buffer = BytesIO(); doc.save(buffer)
            response = await client.post(f'/api/contracts/{cid}/versions/upload', files={'file':('demo.docx',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert response.status_code == 200, response.status_code
            vid = response.json()['data']['version_id']
            first_run_id = response.json()['data']['run_id']
            report = (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).json()['data']
            print('Analysis status:', report['status'], flush=True)
            assert report['status'] == 'completed', report.get('error')
            assert report['document_text'] and report['result']['summary']
            print('Risk count:', len(report['result']['risks']), flush=True)
            repeated = (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).json()['data']
            assert repeated['result'] == report['result']
            listed = (await client.get(f'/api/contracts/{cid}/versions')).json()['data']['versions']
            assert listed[-1]['status'] == 'completed'

            # Two workers may receive the same callback, but only one may claim the run.
            async with SessionLocal() as db:
                claim_run = AnalysisRunModel(version_id=UUID(vid), status='pending')
                db.add(claim_run)
                await db.commit()
                claim_run_id = claim_run.id
            from products.contract.schemas.analysis import ContractAnalysis
            claim_review = AsyncMock(return_value=ContractAnalysis(document_type='测试', summary='原子领取测试'))
            with patch('products.contract.agents.review_agent.analyze_text', claim_review), patch(
                'infrastructure.document.contract_source.OssContractDocumentParser.parse',
                AsyncMock(side_effect=AssertionError('cached content should be reused')),
            ):
                await asyncio.gather(execute_analysis(claim_run_id), execute_analysis(claim_run_id))
            assert claim_review.await_count == 1
            async with SessionLocal() as db:
                claimed = await db.get(AnalysisRunModel, claim_run_id)
                claimed_version = await db.get(ContractVersionModel, UUID(vid))
                assert claimed.status == 'completed'
                assert claimed_version.status == 'completed'
            print('Atomic analysis claim and version status passed', flush=True)
            history = (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis-runs')).json()['data']
            assert len(history['runs']) == 2
            selected = await client.post(
                f'/api/contracts/{cid}/versions/{vid}/analysis-runs/{first_run_id}/select'
            )
            assert selected.status_code == 200
            selected_report = selected.json()['data']
            assert selected_report['selected_run_id'] == first_run_id
            assert selected_report['is_showing_previous'] is True
            print('Analysis history selection passed', flush=True)

            bad_upload = await client.post(f'/api/contracts/{cid}/versions/upload', files={'file': ('bad.pdf', b'invalid', 'application/pdf')})
            assert bad_upload.status_code == 422
            # Exercise concurrent version allocation without extra model charges.
            fake_review = AsyncMock(return_value=ContractAnalysis(document_type='测试', summary='测试分析'))
            with patch('products.contract.agents.review_agent.analyze_text', fake_review):
                uploads = await asyncio.gather(*[
                    client.post(f'/api/contracts/{cid}/versions/upload', files={'file': ('demo.docx', buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
                    for _ in range(2)
                ])
                assert all(r.status_code == 200 for r in uploads)
                listed = (await client.get(f'/api/contracts/{cid}/versions')).json()['data']['versions']
                assert [v['number'] for v in listed] == [1, 2, 3]
                retried = await client.post(f'/api/contracts/{cid}/versions/{vid}/analyze')
                assert retried.status_code == 200
                assert (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).json()['data']['status'] == 'completed'
            print('Invalid upload, concurrent versions, and retry passed', flush=True)
            # A different identity must not retrieve the fixture's text.
            app.dependency_overrides[require_user] = lambda: User(user_id=-1)
            assert (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).status_code == 404
            print('Persistence and ownership checks passed', flush=True)
    finally:
        app.dependency_overrides.pop(require_user, None)
        async with SessionLocal() as db:
            ids = list((await db.scalars(select(ContractModel.id).where(ContractModel.user_id == user_id))).all())
            versions = list((await db.scalars(select(ContractVersionModel).where(ContractVersionModel.contract_id.in_(ids)))).all())
            for version in versions:
                await asyncio.to_thread(delete_object, version.source_key)
            await db.execute(delete(AnalysisRunModel).where(AnalysisRunModel.version_id.in_([v.id for v in versions])))
            await db.execute(delete(ContractVersionModel).where(ContractVersionModel.contract_id.in_(ids)))
            await db.execute(delete(ContractModel).where(ContractModel.user_id == user_id))
            await db.execute(delete(CustomerModel).where(CustomerModel.user_id == user_id))
            await db.execute(delete(User).where(User.user_id == user_id))
            await db.commit()
        await engine.dispose()
        print('Synthetic test records and OSS file removed', flush=True)


if __name__ == '__main__':
    import sys
    if '--mock-review' in sys.argv:
        from products.contract.schemas.analysis import ContractAnalysis
        with patch('products.contract.agents.review_agent.analyze_text', AsyncMock(return_value=ContractAnalysis(document_type='测试', summary='测试分析'))):
            asyncio.run(main())
    else:
        asyncio.run(main())
