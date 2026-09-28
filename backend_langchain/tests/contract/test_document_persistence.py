import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from products.contract.models import (
    CanonicalContractClauseModel,
    ContractDocumentBlockModel,
    ContractVersionModel,
)
from products.contract.document_intelligence.clauses import ground_candidates
from products.contract.schemas.document import ClauseCandidate
from dataclasses import replace
from products.contract import db as contract_db
from products.contract.domain.document import DocumentBlock, ParsedDocument


def document(version_id):
    return ParsedDocument(version_id, 'source',
        (DocumentBlock(uuid4(), version_id, 1, 'source', page=2),), 2, 'pdfplumber')


def test_blocks_reuse_unique_sequence_and_cascade(document_db):
    factory, version_id = document_db
    parsed = document(version_id)

    async def run():
        async with factory() as session:
            for _ in range(2):
                async with session.begin():
                    await contract_db.save_parsed_document(session, parsed)
            async with session.begin():
                assert await contract_db.get_parsed_document(session, version_id) == parsed
                assert await session.scalar(select(func.count()).select_from(ContractDocumentBlockModel)) == 1
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(ContractDocumentBlockModel(id=uuid4(), version_id=version_id,
                        sequence=1, text='duplicate', type='paragraph'))
            async with session.begin():
                await session.execute(delete(ContractVersionModel).where(ContractVersionModel.id == version_id))
            async with session.begin():
                assert await session.scalar(select(func.count()).select_from(ContractDocumentBlockModel)) == 0
    asyncio.run(run())


def test_blocks_and_content_rollback_together(document_db):
    factory, version_id = document_db

    async def run():
        async with factory() as session:
            with pytest.raises(RuntimeError):
                async with session.begin():
                    await contract_db.save_parsed_document(session, document(version_id))
                    raise RuntimeError('rollback')
            async with session.begin():
                assert await contract_db.get_content(session, version_id) is None
                assert await contract_db.get_parsed_document(session, version_id) is None
    asyncio.run(run())


def test_canonical_reuse_source_validation_unique_sequence_and_rollback(document_db):
    factory, version_id = document_db
    parsed = document(version_id)
    clauses = ground_candidates(version_id, parsed.blocks, [ClauseCandidate(
        title='付款', source_block_ids=[parsed.blocks[0].block_id])])

    async def run():
        async with factory() as session:
            with pytest.raises(RuntimeError):
                async with session.begin():
                    await contract_db.save_parsed_document(session, parsed)
                    await contract_db.save_canonical_clauses(session, version_id, clauses, 'v1')
                    raise RuntimeError('publication failed')
            async with session.begin():
                assert await contract_db.get_parsed_document(session, version_id) is None
                assert await contract_db.get_canonical_clauses(session, version_id) == ()
            for _ in range(2):
                async with session.begin():
                    await contract_db.save_parsed_document(session, parsed)
                    await contract_db.save_canonical_clauses(session, version_id, clauses, 'v1')
            async with session.begin():
                assert await contract_db.get_canonical_clauses(session, version_id) == clauses
                assert await session.scalar(select(func.count()).select_from(CanonicalContractClauseModel)) == 1
            for invalid in [replace(clauses[0], source_block_ids=(uuid4(),)),
                            replace(clauses[0], version_id=uuid4()),
                            replace(clauses[0], original_text='fabricated')]:
                with pytest.raises(ValueError):
                    async with session.begin():
                        await contract_db.save_canonical_clauses(session, version_id, (invalid,), 'v1')
            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(CanonicalContractClauseModel(id=uuid4(), version_id=version_id, sequence=1,
                        title='duplicate', clause_type='other', original_text='source',
                        source_block_ids=[], pages=[], intelligence_version='v1'))
            async with session.begin():
                assert await contract_db.get_canonical_clauses(session, version_id) == clauses
    asyncio.run(run())
