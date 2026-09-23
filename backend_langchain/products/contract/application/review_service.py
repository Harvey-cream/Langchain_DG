from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from agent_platform.storage import ObjectStoragePort
from products.contract.application.ports import ContractReviewStore, JobDispatcher
from products.contract.domain.review import ReviewRunRecord, ReviewSnapshot


class ContractReviewError(Exception):
    """Contract Review 用例错误基类，由 HTTP 边界负责状态码映射。"""


class ContractNotFoundError(ContractReviewError):
    pass


class ContractVersionNotFoundError(ContractReviewError):
    pass


class ContractVersionSourceError(ContractReviewError):
    pass


class AnalysisRunNotSelectableError(ContractReviewError):
    pass


UploadValidator = Callable[[str, bytes], str]


class ContractReviewService:
    """Contract Review 的单一用例入口。

    Service 负责权限、版本/任务初始化、事务与提交后的任务派发；Store 只做数据访问。
    """

    def __init__(
        self,
        *,
        session: Any,
        store: ContractReviewStore,
        storage: ObjectStoragePort,
        validate_upload: UploadValidator,
        dispatcher: JobDispatcher,
    ) -> None:
        self.session = session
        self.store = store
        self.storage = storage
        self.validate_upload = validate_upload
        self.dispatcher = dispatcher

    async def upload_contract_version(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        filename: str,
        data: bytes,
    ) -> tuple[Any, Any]:
        safe_filename = (filename or "contract").replace("\\", "/").split("/")[-1]
        kind = self.validate_upload(safe_filename, data)

        # 上传 OSS 前只做一次短权限查询，不能持有 Contract 行锁跨越网络 IO。
        async with self.session.begin():
            if await self.store.get_owned_contract(user_id, contract_id) is None:
                raise ContractNotFoundError("合同不存在")

        version_id = uuid4()
        source_key = (
            f"contracts/{user_id}/{contract_id}/{version_id}/original.{kind}"
        )
        content_type = (
            "application/pdf"
            if kind == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        await asyncio.to_thread(
            self.storage.put,
            source_key,
            data,
            content_type=content_type,
        )

        try:
            async with self.session.begin():
                # OSS 上传期间 Contract 可能被删除，因此写入前重新校验并加锁。
                if await self.store.lock_owned_contract(user_id, contract_id) is None:
                    raise ContractNotFoundError("合同不存在")
                number = await self.store.get_next_version_number(contract_id)
                version = await self.store.create_version(
                    version_id=version_id,
                    contract_id=contract_id,
                    number=number,
                    source_key=source_key,
                    filename=safe_filename,
                    status="pending",
                )
                run = await self.store.create_run(
                    version_id=version_id,
                    attempt=1,
                    prompt_version="v2",
                )
        except Exception:
            await asyncio.to_thread(self.storage.delete, source_key)
            raise

        await self.dispatcher.dispatch_analysis(run.id)
        return version, run

    async def retry_analysis(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> tuple[Any, bool]:
        created = False
        async with self.session.begin():
            version = await self.store.lock_owned_version(
                user_id, contract_id, version_id
            )
            if version is None:
                raise ContractVersionNotFoundError("合同版本不存在")
            expected = f"contracts/{user_id}/{contract_id}/{version_id}/original."
            if version.source_key not in (expected + "pdf", expected + "docx"):
                raise ContractVersionSourceError("请通过文件上传创建版本后再分析")

            run = await self.store.get_active_run(version_id)
            if run is None:
                attempt = await self.store.get_max_attempt(version_id) + 1
                run = await self.store.create_run(
                    version_id=version_id,
                    attempt=attempt,
                    prompt_version="v2",
                )
                await self.store.set_version_status(version, "pending")
                created = True

        if created:
            await self.dispatcher.dispatch_analysis(run.id)
        return run, created

    async def get_analysis(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ReviewSnapshot:
        snapshot = await self.store.load_snapshot(user_id, contract_id, version_id)
        if snapshot is None:
            raise ContractVersionNotFoundError("合同版本不存在")
        return snapshot

    async def get_analysis_history(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> list[ReviewRunRecord]:
        runs = await self.store.list_history(user_id, contract_id, version_id)
        if runs is None:
            raise ContractVersionNotFoundError("合同版本不存在")
        return runs

    async def select_analysis_run(
        self,
        *,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
        run_id: UUID,
    ) -> ReviewSnapshot:
        async with self.session.begin():
            selected = await self.store.select_run(
                user_id, contract_id, version_id, run_id
            )
            if not selected:
                raise AnalysisRunNotSelectableError(
                    "可回退的成功分析记录不存在"
                )
        return await self.get_analysis(
            user_id=user_id,
            contract_id=contract_id,
            version_id=version_id,
        )
