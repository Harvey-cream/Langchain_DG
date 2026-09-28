"""PostgreSQL fact publication concurrency on a disposable database only."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
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
)
from products.contract import db as contract_db
from products.contract.document_intelligence.pipeline import DocumentIntelligencePipeline
from products.contract.domain.document import DocumentBlock, ParsedDocument
from products.contract.domain.review import ReviewContext
from products.contract.schemas.document import ClauseCandidate, ClauseExtraction, DocumentMetadata, SectionCandidate, SectionExtraction
from scripts.contract.test_contract_migration_postgres import (
    BACKEND_ROOT,
    _drop_database,
    _psycopg_url,
    _url,
)
from common.settings import POSTGRES_DATABASE


class FakeDocumentCapabilities:
    async def sections(self, blocks):
        return SectionExtraction(sections=[SectionCandidate(title='正文', source_block_ids=[b.block_id for b in blocks])])

    async def clauses(self, blocks):
        return ClauseExtraction(clauses=[ClauseCandidate(title='条款', source_block_ids=[b.block_id for b in blocks])])

    async def metadata(self, blocks):
        return DocumentMetadata(summary='事实')


async def verify(database_name):
    engine = create_async_engine(_url(database_name).set(drivername='postgresql+asyncpg'))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    version_id, contract_id = uuid4(), uuid4()
    try:
        async with factory() as session, session.begin():
            session.add(User(user_id=1, username='facts', email='facts@test.invalid', password='test'))
            await session.flush()
            session.add(CustomerModel(id=1, user_id=1, name='test', email='test@test.invalid'))
            await session.flush()
            session.add(ContractModel(id=contract_id, user_id=1, customer_id=1, title='test'))
            await session.flush()
            session.add(ContractVersionModel(id=version_id, contract_id=contract_id, number=1,
                filename='test.pdf', source_key='unused'))

        both_parsing = asyncio.Event()
        parse_calls = 0
        block = DocumentBlock(uuid4(), version_id, 1, '第一条 真实原文', page=1)
        parsed = ParsedDocument(version_id, block.text, (block,), 1, 'pdfplumber')

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
                return await pipeline.ensure(ReviewContext(uuid4(), version_id, 'unused', 'test.pdf'))

        first, second = await asyncio.gather(publish(), publish())
        assert first == second
        assert parse_calls == 2  # Both passed the initial cache miss before either published.
        async with factory() as session:
            for model in (ContractDocumentBlockModel, CanonicalContractClauseModel, ContractDocumentFactsModel):
                assert await session.scalar(select(func.count()).select_from(model)) == 1
            assert await contract_db.get_document_facts(session, version_id) == first
        print('PostgreSQL concurrent Document Facts publishers: one identical fact set, passed', flush=True)
    finally:
        await engine.dispose()


def main():
    database_name = f'contract_facts_test_{uuid4().hex[:12]}'
    print(f'Creating disposable database {database_name}', flush=True)
    with psycopg.connect(_psycopg_url(POSTGRES_DATABASE), autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
    engine = create_engine(_url(database_name), connect_args={'connect_timeout': 5})
    try:
        User.__table__.create(engine)
        config = Config(str(BACKEND_ROOT / 'alembic.ini'))
        config.set_main_option('sqlalchemy.url', _url(database_name).render_as_string(hide_password=False))
        command.upgrade(config, 'head')
        asyncio.run(verify(database_name))
    finally:
        engine.dispose()
        with psycopg.connect(_psycopg_url(POSTGRES_DATABASE), autocommit=True, connect_timeout=5) as admin:
            _drop_database(admin, database_name)
        print(f'Removed disposable database {database_name}', flush=True)


if __name__ == '__main__':
    main()
