from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from infrastructure.db.repositories.contract import (
    SqlAlchemyContractRepository,
    SqlAlchemyContractVersionRepository,
    SqlAlchemyCustomerRepository,
)
from infrastructure.db.repositories.contract_review_query import (
    SqlAlchemyContractReviewQueryRepository,
)
from products.contract.application.review_service import ContractReviewApplicationService
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
        commit=_commit(session),
    )


def get_contract_review_service(
    session: AsyncSession = Depends(get_db),
) -> ContractReviewApplicationService:
    return ContractReviewApplicationService(
        SqlAlchemyContractReviewQueryRepository(session)
    )
