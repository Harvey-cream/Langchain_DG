from collections.abc import Callable

from fastapi import BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from infrastructure.db.repositories.contract import (
    SqlAlchemyContractRepository,
    SqlAlchemyContractVersionRepository,
    SqlAlchemyCustomerRepository,
)
from infrastructure.db.repositories.contract_review_store import (
    SqlAlchemyContractReviewStore,
)
from infrastructure.document.contract_parser import validate_file
from infrastructure.oss.adapter import OssObjectStorage
from infrastructure.queue.background_tasks import FastApiBackgroundJobDispatcher
from products.contract.application.review_service import ContractReviewService
from products.contract.application.services import (
    ContractApplicationService,
    ContractVersionApplicationService,
    CustomerApplicationService,
)


def _commit(session: AsyncSession) -> Callable:
    async def commit() -> None:
        await session.commit()

    return commit


def get_customer_service(session: AsyncSession = Depends(get_db)) -> CustomerApplicationService:
    return CustomerApplicationService(SqlAlchemyCustomerRepository(session), commit=_commit(session))


def get_contract_service(session: AsyncSession = Depends(get_db)) -> ContractApplicationService:
    return ContractApplicationService(
        SqlAlchemyContractRepository(session),
        SqlAlchemyCustomerRepository(session),
        commit=_commit(session),
    )


def get_contract_version_service(session: AsyncSession = Depends(get_db)) -> ContractVersionApplicationService:
    return ContractVersionApplicationService(
        SqlAlchemyContractVersionRepository(session),
        SqlAlchemyContractRepository(session),
        session=session,
        review_store=SqlAlchemyContractReviewStore(session),
    )


def get_contract_review_service(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> ContractReviewService:
    return ContractReviewService(
        session=session,
        store=SqlAlchemyContractReviewStore(session),
        storage=OssObjectStorage(),
        validate_upload=validate_file,
        dispatcher=FastApiBackgroundJobDispatcher(background_tasks),
    )
