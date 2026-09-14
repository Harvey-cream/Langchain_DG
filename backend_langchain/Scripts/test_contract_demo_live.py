"""Explicit live smoke test with synthetic data; removes only its own fixtures."""
import asyncio
import secrets
from io import BytesIO
from uuid import uuid4
import httpx
from unittest.mock import AsyncMock, patch
from docx import Document
from sqlalchemy import delete, select
from app.main import app
from app.db import engine, SessionLocal
from app.deps import require_user
from app.models import User, Base
from infrastructure.db.models import CustomerModel, ContractModel, ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from app.services.oss_client import delete_object


async def main():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
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
            report = (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).json()['data']
            print('Analysis status:', report['status'], flush=True)
            assert report['status'] == 'completed', report.get('error')
            assert report['document_text'] and report['result']['summary']
            print('Risk count:', len(report['result']['risks']), flush=True)
            repeated = (await client.get(f'/api/contracts/{cid}/versions/{vid}/analysis')).json()['data']
            assert repeated['result'] == report['result']
            bad_upload = await client.post(f'/api/contracts/{cid}/versions/upload', files={'file': ('bad.pdf', b'invalid', 'application/pdf')})
            assert bad_upload.status_code == 422
            # Exercise concurrent version allocation without extra model charges.
            from products.contract.schemas.analysis import ContractAnalysis
            fake_review = AsyncMock(return_value=ContractAnalysis(document_type='测试', summary='测试分析'))
            with patch('infrastructure.document.contract_jobs.analyze_text', fake_review):
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
        with patch('infrastructure.document.contract_jobs.analyze_text', AsyncMock(return_value=ContractAnalysis(document_type='测试', summary='测试分析'))):
            asyncio.run(main())
    else:
        asyncio.run(main())
