from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.deps import require_user
from app.dependencies.contract import get_contract_service, get_contract_version_service
from app.models import User
from app.response import fail, ok
from products.contract.application.services import ContractApplicationService, ContractVersionApplicationService
from products.contract.schemas import ContractCreate, ContractResponse, ContractVersionCreate, ContractVersionResponse

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _contract_response(item) -> dict:
    return ContractResponse.model_validate(item).model_dump(mode="json")


def _version_response(item) -> dict:
    return ContractVersionResponse.model_validate(item).model_dump(mode="json")


@router.post("")
async def create_contract(
    body: ContractCreate,
    user: User = Depends(require_user),
    service: ContractApplicationService = Depends(get_contract_service),
):
    try:
        contract = await service.create(user_id=user.user_id, customer_id=body.customer_id, title=body.title)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    except ValueError as exc:
        return fail(str(exc), status_code=400)
    return ok("合同创建成功", _contract_response(contract))


@router.get("")
async def list_contracts(
    user: User = Depends(require_user),
    service: ContractApplicationService = Depends(get_contract_service),
):
    return ok("获取合同成功", {"contracts": [_contract_response(item) for item in await service.list(user_id=user.user_id)]})


@router.get("/{contract_id}")
async def get_contract(
    contract_id: UUID,
    user: User = Depends(require_user),
    service: ContractApplicationService = Depends(get_contract_service),
):
    try:
        contract = await service.get(user_id=user.user_id, contract_id=contract_id)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    return ok("获取合同成功", _contract_response(contract))


@router.post("/{contract_id}/versions")
async def create_contract_version(
    contract_id: UUID,
    body: ContractVersionCreate,
    user: User = Depends(require_user),
    service: ContractVersionApplicationService = Depends(get_contract_version_service),
):
    try:
        version = await service.create(user_id=user.user_id, contract_id=contract_id, source_key=body.source_key, filename=body.filename)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    except ValueError as exc:
        return fail(str(exc), status_code=400)
    return ok("合同版本创建成功", _version_response(version))


@router.get("/{contract_id}/versions")
async def list_contract_versions(
    contract_id: UUID,
    user: User = Depends(require_user),
    service: ContractVersionApplicationService = Depends(get_contract_version_service),
):
    try:
        versions = await service.list(user_id=user.user_id, contract_id=contract_id)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    return ok("获取合同版本成功", {"versions": [_version_response(item) for item in versions]})


@router.get("/{contract_id}/versions/{version_id}")
async def get_contract_version(
    contract_id: UUID,
    version_id: UUID,
    user: User = Depends(require_user),
    service: ContractVersionApplicationService = Depends(get_contract_version_service),
):
    try:
        version = await service.get(user_id=user.user_id, contract_id=contract_id, version_id=version_id)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    return ok("获取合同版本成功", _version_response(version))
