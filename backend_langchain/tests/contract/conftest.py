"""Real SQL transactions against an Alembic-created disposable SQLite database."""
import asyncio
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from common.account.models import User
from products.contract.models import ContractModel, ContractVersionModel, CustomerModel


@pytest.fixture
def document_db(tmp_path):
    path = tmp_path / 'facts.sqlite'
    url = f'sqlite:///{path.as_posix()}'
    engine = create_engine(url)
    User.__table__.create(engine)
    engine.dispose()
    config = Config('alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    command.upgrade(config, 'head')
    async_engine = create_async_engine(url.replace('sqlite:', 'sqlite+aiosqlite:'))

    @event.listens_for(async_engine.sync_engine, 'connect')
    def enable_fk(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    version_id, contract_id = uuid4(), uuid4()

    async def seed():
        async with factory() as session, session.begin():
            session.add(User(user_id=1, email='facts@test.invalid', username='test', password='test'))
            await session.flush()
            session.add(CustomerModel(id=1, user_id=1, name='test', email='customer@test.invalid'))
            await session.flush()
            session.add(ContractModel(id=contract_id, user_id=1, customer_id=1, title='test'))
            await session.flush()
            session.add(ContractVersionModel(id=version_id, contract_id=contract_id, number=1,
                source_key='test', filename='test.docx'))

    asyncio.run(seed())
    yield factory, version_id
    asyncio.run(async_engine.dispose())
