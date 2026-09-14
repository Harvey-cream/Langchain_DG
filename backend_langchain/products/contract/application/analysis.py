"""Contract analysis use case; execution and persistence belong to adapters."""
from typing import Awaitable, Callable
from products.contract.schemas.analysis import ContractAnalysis


async def review_document(text: str, review: Callable[[str], Awaitable[ContractAnalysis]]) -> ContractAnalysis:
    compact = ''.join(text.split())
    for _ in range(2):
        result = await review(text)
        if all(risk.original_text.strip() and ''.join(risk.original_text.split()) in compact for risk in result.risks):
            return result
    raise ValueError('AI 引用原文校验失败，请重新分析')
