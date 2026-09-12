from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from products.contract.application.ports import (
    ContractRepository,
    ContractVersionRepository,
    CustomerRepository,
)
from products.contract.domain.contract import Contract
from products.contract.domain.customer import Customer
from products.contract.domain.version import ContractVersion
from infrastructure.db.models import ContractModel, ContractVersionModel, CustomerModel


class SqlAlchemyCustomerRepository(CustomerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, customer: Customer) -> Customer:
        model = CustomerModel(user_id=customer.user_id, name=customer.name, email=customer.email)
        self.session.add(model)
        await self.session.flush()
        return _customer_entity(model)

    async def get(self, user_id: int, customer_id: int) -> Customer | None:
        result = await self.session.execute(
            select(CustomerModel).where(CustomerModel.user_id == user_id, CustomerModel.id == customer_id)
        )
        model = result.scalar_one_or_none()
        return _customer_entity(model) if model else None

    async def list(self, user_id: int) -> list[Customer]:
        result = await self.session.execute(
            select(CustomerModel).where(CustomerModel.user_id == user_id).order_by(CustomerModel.created_at)
        )
        return [_customer_entity(model) for model in result.scalars()]

    async def update(self, customer: Customer) -> Customer:
        model = await self.session.get(CustomerModel, customer.id)
        if model is None or model.user_id != customer.user_id:
            raise LookupError("customer not found")
        model.name, model.email = customer.name, customer.email
        await self.session.flush()
        return _customer_entity(model)

    async def delete(self, user_id: int, customer_id: int) -> bool:
        model = await self.session.get(CustomerModel, customer_id)
        if model is None or model.user_id != user_id:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True


class SqlAlchemyContractRepository(ContractRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, contract: Contract) -> Contract:
        model = ContractModel(id=contract.id, user_id=contract.user_id, customer_id=contract.customer_id, title=contract.title)
        self.session.add(model)
        await self.session.flush()
        return _contract_entity(model)

    async def get(self, user_id: int, contract_id: UUID) -> Contract | None:
        result = await self.session.execute(
            select(ContractModel).where(ContractModel.user_id == user_id, ContractModel.id == contract_id)
        )
        model = result.scalar_one_or_none()
        return _contract_entity(model) if model else None

    async def list(self, user_id: int) -> list[Contract]:
        result = await self.session.execute(
            select(ContractModel).where(ContractModel.user_id == user_id).order_by(ContractModel.created_at)
        )
        return [_contract_entity(model) for model in result.scalars()]


class SqlAlchemyContractVersionRepository(ContractVersionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, version: ContractVersion) -> ContractVersion:
        model = ContractVersionModel(
            id=version.id, contract_id=version.contract_id, number=version.number,
            source_key=version.source_key, filename=version.filename, status=version.status,
        )
        self.session.add(model)
        await self.session.flush()
        return _version_entity(model)

    async def get(self, user_id: int, version_id: UUID) -> ContractVersion | None:
        result = await self.session.execute(
            select(ContractVersionModel).join(ContractModel, ContractModel.id == ContractVersionModel.contract_id).where(
                ContractModel.user_id == user_id, ContractVersionModel.id == version_id
            )
        )
        model = result.scalar_one_or_none()
        return _version_entity(model) if model else None

    async def list(self, user_id: int, contract_id: UUID) -> list[ContractVersion]:
        result = await self.session.execute(
            select(ContractVersionModel).join(ContractModel, ContractModel.id == ContractVersionModel.contract_id).where(
                ContractModel.user_id == user_id, ContractVersionModel.contract_id == contract_id
            ).order_by(ContractVersionModel.number)
        )
        return [_version_entity(model) for model in result.scalars()]


def _customer_entity(model: CustomerModel) -> Customer:
    return Customer(id=model.id, user_id=model.user_id, name=model.name, email=model.email, created_at=model.created_at, updated_at=model.updated_at)


def _contract_entity(model: ContractModel) -> Contract:
    return Contract(id=model.id, user_id=model.user_id, customer_id=model.customer_id, title=model.title, created_at=model.created_at, updated_at=model.updated_at)


def _version_entity(model: ContractVersionModel) -> ContractVersion:
    return ContractVersion(id=model.id, contract_id=model.contract_id, number=model.number, source_key=model.source_key, filename=model.filename, status=model.status, created_at=model.created_at)
