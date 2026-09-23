"""Contract analysis use case; execution and persistence belong to adapters."""
from typing import Awaitable, Callable
from products.contract.policies.evidence_validation import validate_evidence
from products.contract.schemas.analysis import ContractAnalysis


async def review_document(text: str, review: Callable[[str], Awaitable[ContractAnalysis]]) -> ContractAnalysis:
    for _ in range(2):
        result = await review(text)
        if validate_evidence(text, result):
            return result
    raise ValueError('AI 引用原文校验失败，请重新分析')
