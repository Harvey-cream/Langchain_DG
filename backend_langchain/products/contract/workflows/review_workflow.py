from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from pydantic import ValidationError

from products.contract.application.ports import ContractReviewStore
from products.contract.application.analysis import review_document
from products.contract.workflows.ports import (
    ContractDocumentParser,
    ContractReviewer,
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
        session,
        store: ContractReviewStore,
        parser: ContractDocumentParser,
        reviewer: ContractReviewer,
        *,
        timeout_seconds: int = 240,
    ) -> None:
        self.session = session
        self.store = store
        self.parser = parser
        self.reviewer = reviewer
        self.timeout_seconds = timeout_seconds

    async def run(self, run_id: UUID) -> None:
        try:
            # T1: 原子领取任务，并读取版本级缓存；立即提交领取结果。
            async with self.session.begin():
                context = await self.store.claim_run(run_id)
                if context is None:
                    return
                content = await self.store.get_content(context.version_id)
                if content is None:
                    await self.store.mark_parsing(context)

            if content is None:
                # Parser/OSS 是长 IO，必须在事务外执行。
                content = await self.parser.parse(context)
                # T2: 单独持久化解析缓存。
                async with self.session.begin():
                    await self.store.save_content(content)

            # T3: 进入分析态后立即提交，再调用 LLM。
            async with self.session.begin():
                await self.store.mark_analyzing(context)

            # Reviewer/LLM 是长 IO，必须在事务外执行。
            result = await asyncio.wait_for(
                review_document(content.document_text, self.reviewer.review),
                timeout=self.timeout_seconds,
            )

            # T4: Clause/Risk/result/selection 与完成状态原子落库。
            async with self.session.begin():
                await self.store.complete_run(context, result)
        except Exception as exc:
            logger.exception("contract review workflow failed run_id=%s", run_id)
            # 若异常发生在事务块内，begin() 已回滚；兜底处理外部实现留下的事务。
            in_transaction = getattr(self.session, "in_transaction", None)
            if callable(in_transaction) and in_transaction():
                await self.session.rollback()
            # 失败状态使用独立短事务，不能依赖已失败的事务。
            async with self.session.begin():
                await self.store.fail_run(run_id, review_error_message(exc))
