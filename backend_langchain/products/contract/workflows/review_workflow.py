from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from pydantic import ValidationError

from products.contract.application.analysis import review_document
from products.contract.workflows.ports import (
    ContractDocumentParser,
    ContractReviewer,
    ContractReviewRepository,
)

logger = logging.getLogger(__name__)


def review_error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "AI 返回格式不符合要求，请重新分析"
    if isinstance(exc, ValueError):
        return str(exc)
    return "分析服务暂不可用或超时，请稍后重新分析"


class ContractReviewWorkflow:
    def __init__(
        self,
        repository: ContractReviewRepository,
        parser: ContractDocumentParser,
        reviewer: ContractReviewer,
        *,
        timeout_seconds: int = 240,
    ) -> None:
        self.repository = repository
        self.parser = parser
        self.reviewer = reviewer
        self.timeout_seconds = timeout_seconds

    async def run(self, run_id: UUID) -> None:
        try:
            context = await self.repository.claim(run_id)
            if context is None:
                return
            content = await self.repository.get_content(context.version_id)
            if content is None:
                await self.repository.mark_parsing(context)
                content = await self.parser.parse(context)
                await self.repository.save_content(content)

            await self.repository.mark_analyzing(context)
            result = await asyncio.wait_for(
                review_document(content.document_text, self.reviewer.review),
                timeout=self.timeout_seconds,
            )
            await self.repository.complete(context, result)
        except Exception as exc:
            logger.exception("contract review workflow failed run_id=%s", run_id)
            await self.repository.fail(run_id, review_error_message(exc))
