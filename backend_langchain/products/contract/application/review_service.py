from __future__ import annotations

from typing import Protocol
from uuid import UUID

from products.contract.domain.review import ReviewRunRecord, ReviewSnapshot


class ContractReviewQueryRepository(Protocol):
    async def load_snapshot(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ReviewSnapshot | None: ...

    async def list_runs(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> list[ReviewRunRecord] | None: ...

    async def select_run(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
        run_id: UUID,
    ) -> bool: ...


class ContractReviewApplicationService:
    def __init__(self, repository: ContractReviewQueryRepository):
        self.repository = repository

    async def get(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ReviewSnapshot:
        snapshot = await self.repository.load_snapshot(user_id, contract_id, version_id)
        if snapshot is None:
            raise LookupError("合同版本不存在")
        return snapshot

    async def history(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> list[ReviewRunRecord]:
        runs = await self.repository.list_runs(user_id, contract_id, version_id)
        if runs is None:
            raise LookupError("合同版本不存在")
        return runs

    async def select(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
        run_id: UUID,
    ) -> ReviewSnapshot:
        if not await self.repository.select_run(user_id, contract_id, version_id, run_id):
            raise LookupError("可回退的成功分析记录不存在")
        return await self.get(
            user_id=user_id,
            contract_id=contract_id,
            version_id=version_id,
        )
