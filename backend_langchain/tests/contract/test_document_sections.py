import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from products.contract.document_intelligence.sections import block_windows, detect_sections
from products.contract.domain.document import DocumentBlock
from products.contract.schemas.document import SectionCandidate, SectionExtraction


def blocks(texts):
    version_id = uuid4()
    return tuple(DocumentBlock(uuid4(), version_id, i, text) for i, text in enumerate(texts, 1))


@pytest.mark.parametrize('titles', [
    ['第一条 服务内容', '第二条 付款方式'], ['一、服务', '二、费用'],
    ['1. 服务', '1.1 费用', '1.2 期限', '2. 其他'], ['1 服务', '2 付款'],
])
def test_rule_titles_and_consecutive_paragraphs(titles):
    source = blocks([value for title in titles for value in (title, '详细正文', '后续正文')])
    fallback = AsyncMock()
    result = asyncio.run(detect_sections(source, fallback))
    assert len(result) == len(titles)
    assert all(len(s.source_block_ids) == 3 for s in result)
    fallback.assert_not_called()


def test_no_heading_fallback_preserves_table_and_all_blocks():
    source = list(blocks(['前文', '后文', '表格金额']))
    b = source[-1]
    source[-1] = DocumentBlock(b.block_id, b.version_id, b.sequence, b.text, 'table')
    fallback = AsyncMock(return_value=SectionExtraction(sections=[SectionCandidate(
        title='合同', source_block_ids=[b.block_id for b in source])]))
    result = asyncio.run(detect_sections(source, fallback))
    assert result[0].source_block_ids == tuple(b.block_id for b in source)
    fallback.assert_awaited_once()


def test_invalid_boundary_fails_after_two_attempts():
    source = blocks(['正文'])
    fallback = AsyncMock(return_value={'sections': [{'title': 'x', 'source_block_ids': [str(uuid4())]}]})
    with pytest.raises(ValueError, match='Section'):
        asyncio.run(detect_sections(source, fallback))
    assert fallback.await_count == 2


def test_bounded_windows_never_drop_or_truncate_blocks():
    source = blocks(['正文' * 500 for _ in range(100)])
    windows = block_windows(source)
    assert len(windows) > 1
    assert tuple(b for window in windows for b in window) == source
    with pytest.raises(ValueError, match='未截断'):
        block_windows(blocks(['a' * 12000]))
