from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import ValidationError

from products.contract import db as contract_db
from products.contract.schemas.analysis import ContractAnalysis

if TYPE_CHECKING:
    from products.contract.document_intelligence.pipeline import (
        DocumentIntelligencePipeline,
    )

logger = logging.getLogger(__name__)


class ContractReviewer(Protocol):
    async def review(self, document_text: str) -> ContractAnalysis: ...


def _compact(value: str) -> str:
    return "".join(value.split())


def validate_evidence(document_text: str, result: ContractAnalysis) -> bool:
    """Every quoted clause and risk must be grounded in the source document."""
    source = _compact(document_text)
    evidence = [clause.original_text for clause in result.clauses]
    evidence.extend(risk.original_text for risk in result.risks)
    if not all(item.strip() and _compact(item) in source for item in evidence):
        return False
    clause_count = len(result.clauses)
    return all(
        risk.clause_sequence is None
        or 1 <= risk.clause_sequence <= clause_count
        for risk in result.risks
    )


async def review_document(
    text: str,
    review: Callable[[str], Awaitable[ContractAnalysis]],
) -> ContractAnalysis:
    for _ in range(2):
        result = await review(text)
        if validate_evidence(text, result):
            return result
    raise ValueError("AI 引用原文校验失败，请重新分析")


def review_error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "AI 返回格式不符合要求，请重新分析"
    if isinstance(exc, ValueError):
        return str(exc)
    return "分析服务暂不可用或超时，请稍后重新分析"


async def run_contract_review(
    session,
    document_intelligence: DocumentIntelligencePipeline,
    reviewer: ContractReviewer,
    run_id: UUID,
    *,
    timeout_seconds: int = 240,
) -> None:
    """Run one claimed analysis task; database transactions stay short."""
    try:
        # T1: 原子领取任务并立即提交，重复执行者会直接返回。
        async with session.begin():
            context = await contract_db.claim_run(session, run_id)
            if context is None:
                return
            await contract_db.mark_parsing(session, context)

        facts = await asyncio.wait_for(
            document_intelligence.ensure(context),
            timeout=timeout_seconds,
        )

        # T3: 状态提交后再调用 LLM，长 IO 不占用数据库事务。
        async with session.begin():
            await contract_db.mark_analyzing(session, context)

        result = await asyncio.wait_for(
            review_document(facts.document.document_text, reviewer.review),
            timeout=timeout_seconds,
        )

        # T4: Clause、Risk、结果和选中记录一次性提交。
        async with session.begin():
            await contract_db.complete_run(session, context, result)
    except Exception as exc:
        logger.exception("contract review workflow failed run_id=%s", run_id)
        in_transaction = getattr(session, "in_transaction", None)
        if callable(in_transaction) and in_transaction():
            await session.rollback()
        async with session.begin():
            await contract_db.fail_run(session, run_id, review_error_message(exc))
