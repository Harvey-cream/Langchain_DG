from __future__ import annotations

from uuid import UUID

from products.contract.application.ports import (
    ContractRepository,
    ContractVersionRepository,
    CustomerRepository,
)
from products.contract.domain.contract import Contract
from products.contract.domain.customer import Customer
from products.contract.domain.version import ContractVersion


class CustomerApplicationService:
    def __init__(self, repository: CustomerRepository, *, commit):
        self.repository = repository
        self.commit = commit

    async def create(self, *, user_id: int, name: str, email: str) -> Customer:
        customer = Customer.create(user_id=user_id, name=name, email=email)
        result = await self.repository.add(customer)
        await self.commit()
        return result

    async def list(self, *, user_id: int) -> list[Customer]:
        return list(await self.repository.list(user_id))

    async def get(self, *, user_id: int, customer_id: int) -> Customer:
        customer = await self.repository.get(user_id, customer_id)
        if customer is None:
            raise LookupError("customer not found")
        return customer

    async def update(self, *, user_id: int, customer_id: int, name: str, email: str) -> Customer:
        customer = await self.get(user_id=user_id, customer_id=customer_id)
        updated = Customer(id=customer.id, user_id=user_id, name=name.strip(), email=email.strip(), created_at=customer.created_at, updated_at=customer.updated_at)
        if not updated.name or "@" not in updated.email:
            raise ValueError("valid customer name and email are required")
        result = await self.repository.update(updated)
        await self.commit()
        return result

    async def delete(self, *, user_id: int, customer_id: int) -> None:
        if not await self.repository.delete(user_id, customer_id):
            raise LookupError("customer not found")
        await self.commit()


class ContractApplicationService:
    def __init__(self, repository: ContractRepository, customers: CustomerRepository, *, commit):
        self.repository = repository
        self.customers = customers
        self.commit = commit

    async def create(self, *, user_id: int, customer_id: int, title: str) -> Contract:
        if await self.customers.get(user_id, customer_id) is None:
            raise LookupError("customer not found")
        result = await self.repository.add(Contract.create(user_id=user_id, customer_id=customer_id, title=title))
        await self.commit()
        return result

    async def list(self, *, user_id: int) -> list[Contract]:
        return list(await self.repository.list(user_id))

    async def get(self, *, user_id: int, contract_id: UUID) -> Contract:
        contract = await self.repository.get(user_id, contract_id)
        if contract is None:
            raise LookupError("contract not found")
        return contract


class ContractVersionApplicationService:
    def __init__(self, repository: ContractVersionRepository, contracts: ContractRepository, *, commit):
        self.repository = repository
        self.contracts = contracts
        self.commit = commit

    async def create(self, *, user_id: int, contract_id: UUID, source_key: str, filename: str) -> ContractVersion:
        if await self.contracts.get(user_id, contract_id) is None:
            raise LookupError("contract not found")
        versions = await self.repository.list(user_id, contract_id)
        number = ContractVersion.next_number([item.number for item in versions])
        result = await self.repository.add(ContractVersion.create(contract_id=contract_id, number=number, source_key=source_key, filename=filename))
        await self.commit()
        return result

    async def list(self, *, user_id: int, contract_id: UUID) -> list[ContractVersion]:
        if await self.contracts.get(user_id, contract_id) is None:
            raise LookupError("contract not found")
        return list(await self.repository.list(user_id, contract_id))

    async def get(self, *, user_id: int, contract_id: UUID, version_id: UUID) -> ContractVersion:
        version = await self.repository.get(user_id, version_id)
        if version is None or version.contract_id != contract_id:
            raise LookupError("contract version not found")
        return version
