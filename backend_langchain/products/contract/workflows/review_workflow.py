from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import ValidationError

from products.contract import db as contract_db
from products.contract.schemas.analysis import ContractAnalysis
from products.contract.quality import ReviewQualityError
from products.contract.agents.review import ReviewAgent

if TYPE_CHECKING:
    from products.contract.document_intelligence.pipeline import (
        DocumentIntelligencePipeline,
    )

logger = logging.getLogger(__name__)


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
        risk.clause_sequence is None or 1 <= risk.clause_sequence <= clause_count
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
    reviewer: ReviewAgent,
    run_id: UUID,
    *,
    timeout_seconds: int = 240,
) -> None:
    """Task lifecycle only: claim, facts, frozen policy, Graph, atomic publication."""
    output = None
    try:
        async with session.begin():
            context = await contract_db.claim_run(session, run_id)
            if context is None:
                return
            await contract_db.mark_parsing(session, context)

        facts = await asyncio.wait_for(
            document_intelligence.ensure(context),
            timeout=timeout_seconds,
        )
        async with session.begin():
            snapshot = (
                await contract_db.prepare_review_context(session, context)
                if context.user_id is not None
                else {}
            )
            await contract_db.mark_analyzing(session, context)

        # No database transaction spans retrieval, tools or model calls.
        output = await reviewer.review(
            facts.clauses,
            metadata=facts.metadata,
            our_party=context.our_party,
            policies=snapshot.get("policies", []),
            user_id=context.user_id,
            version_id=context.version_id,
            party_role=context.party_role,
            contract_type=context.contract_type,
            timeout_seconds=timeout_seconds,
        )

        # Freeze ONLY sources actually shown to the model. Snapshot + final
        # authoritative gate + findings + completed commit or roll back together.
        async with session.begin():
            for reference in output.used_references:
                await contract_db.record_review_references(
                    session,
                    context,
                    [reference],
                    reference["clause_ids"],
                )
            await contract_db.complete_run(
                session,
                context,
                output.publication_result,
                review_trace=output.review_trace,
                retrieval_events=output.retrieval_events,
            )
    except Exception as exc:
        logger.exception("contract review workflow failed run_id=%s", run_id)
        if session.in_transaction():
            await session.rollback()
        async with session.begin():
            await contract_db.fail_run(
                session,
                run_id,
                review_error_message(exc),
                review_trace=(
                    output.review_trace
                    if output
                    else getattr(exc, "review_trace", None)
                ),
                quality_error=exc if isinstance(exc, ReviewQualityError) else None,
            )
