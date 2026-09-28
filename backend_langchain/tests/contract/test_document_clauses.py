import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from products.contract.document.contract_intelligence import LangChainDocumentIntelligence
from products.contract.document_intelligence.clauses import extract_candidates
from products.contract.document_intelligence.clauses import ground_candidates
from products.contract.schemas.document import ClauseCandidate
from products.contract.domain.document import DocumentBlock
from products.contract.schemas.document import ClauseExtraction


def source():
    version_id = uuid4()
    return [DocumentBlock(uuid4(), version_id, 1, '第一条 付款。'),
            DocumentBlock(uuid4(), version_id, 2, '合同不含任何额外承诺。')]


def candidate(ids, kind='payment'):
    return {'title': '付款', 'clause_type': kind, 'source_block_ids': ids}


def test_normal_multiple_unknown_and_schema_rejects_generated_original_text():
    blocks = source()
    fake = AsyncMock(return_value={'clauses': [candidate([blocks[0].block_id]),
                                              candidate([blocks[1].block_id], 'new_legal_type')]})
    result = asyncio.run(extract_candidates(blocks, fake))
    assert [c.clause_type for c in result] == ['payment', 'other']
    with pytest.raises(ValidationError):
        ClauseExtraction.model_validate({'clauses': [{**candidate([blocks[0].block_id]),
                                                     'original_text': '模型编造正文'}]})


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'reverse', 'empty'])
def test_invalid_extraction_is_explicit_error(case):
    blocks = source()
    ids = [b.block_id for b in blocks]
    values = {'missing': [uuid4()], 'duplicate': [ids[0], ids[0]], 'reverse': ids[::-1]}
    payload = {'clauses': [] if case == 'empty' else [candidate(values[case])]}
    with pytest.raises(ValueError):
        asyncio.run(extract_candidates(blocks, AsyncMock(return_value=payload)))


def test_llm_uses_structured_output_and_untrusted_input_prompt():
    blocks = source()
    structured = Mock(ainvoke=AsyncMock(return_value={'clauses': [candidate([b.block_id for b in blocks])]}))
    model = Mock(with_structured_output=Mock(return_value=structured))
    result = asyncio.run(LangChainDocumentIntelligence(model).clauses(blocks))
    assert len(result.clauses) == 1
    model.with_structured_output.assert_called_once_with(ClauseExtraction, method='function_calling')
    messages = structured.ainvoke.call_args.args[0]
    assert '不可信' in messages[0].content
    assert '不输出 original_text' in messages[0].content
    assert str(blocks[0].block_id) in messages[1].content


def test_original_text_is_exact_deterministic_join_without_rewriting():
    version_id = uuid4()
    blocks = [DocumentBlock(uuid4(), version_id, 1, ' 原文错別字；\t保留！', page=1),
              DocumentBlock(uuid4(), version_id, 2, '表格\t100\n下一行  ', 'table', 2)]
    candidates = [ClauseCandidate(**candidate([b.block_id for b in blocks]))]
    clauses = ground_candidates(version_id, blocks, candidates)
    assert clauses[0].original_text == ' 原文错別字；\t保留！\n\n表格\t100\n下一行  '
    assert clauses[0].pages == (1, 2)
    assert ground_candidates(version_id, blocks, candidates) == clauses
