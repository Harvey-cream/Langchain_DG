import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from products.contract.document_intelligence.clauses import ground_candidates, extract_validated_candidates
from products.contract.document_intelligence.validation import validate_clauses
from products.contract.domain.document import DocumentBlock
from products.contract.schemas.document import ClauseCandidate


def example():
    version_id = uuid4()
    blocks = [DocumentBlock(uuid4(), version_id, i, f'第{i}条 原文') for i in range(1, 4)]
    candidates = [ClauseCandidate(title='原文', source_block_ids=[b.block_id for b in blocks])]
    return version_id, blocks, ground_candidates(version_id, blocks, candidates)


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'reverse', 'cross_version',
                                  'empty', 'rewrite', 'overlap', 'pages'])
def test_grounding_rejects_invalid_facts(case):
    version_id, blocks, clauses = example()
    c = clauses[0]
    if case == 'missing':
        clauses = [replace(c, source_block_ids=(uuid4(),))]
    elif case == 'duplicate':
        clauses = [replace(c, source_block_ids=(blocks[0].block_id,) * 2)]
    elif case == 'reverse':
        clauses = [replace(c, source_block_ids=c.source_block_ids[::-1])]
    elif case == 'cross_version':
        blocks[0] = replace(blocks[0], version_id=uuid4())
    elif case == 'empty':
        clauses = [replace(c, original_text='')]
    elif case == 'rewrite':
        clauses = [replace(c, original_text='模型改写')]
    elif case == 'overlap':
        clauses = [c, replace(c, id=uuid4(), sequence=2)]
    elif case == 'pages':
        clauses = [replace(c, pages=(99,))]
    with pytest.raises(ValueError):
        validate_clauses(version_id, blocks, clauses)


def test_coverage_counts_meaningful_blocks_and_warns_without_failing():
    version_id, blocks, clauses = example()
    report = validate_clauses(version_id, blocks, clauses)
    assert (report.covered_meaningful_blocks, report.total_meaningful_blocks, report.ratio) == (3, 3, 1)
    blocks.append(DocumentBlock(uuid4(), version_id, 4, '未覆盖正文'))
    blocks.append(DocumentBlock(uuid4(), version_id, 5, '---'))
    report = validate_clauses(version_id, blocks, clauses)
    assert (report.covered_meaningful_blocks, report.total_meaningful_blocks, report.ratio) == (3, 4, .75)
    assert report.warnings


def test_invalid_output_retried_once_then_fails_or_recovers():
    version_id, blocks, _ = example()
    invalid = {'clauses': [{'title': 'bad', 'source_block_ids': [str(uuid4())]}]}
    valid = {'clauses': [{'title': 'good', 'source_block_ids': [str(b.block_id) for b in blocks]}]}
    fake = AsyncMock(side_effect=[invalid, valid])
    assert asyncio.run(extract_validated_candidates(version_id, blocks, fake))
    assert fake.await_count == 2
    fake = AsyncMock(return_value=invalid)
    with pytest.raises(ValueError, match='Clause 校验失败'):
        asyncio.run(extract_validated_candidates(version_id, blocks, fake))
    assert fake.await_count == 2
