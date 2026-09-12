from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import require_user
from app.dependencies.contract import get_customer_service
from app.response import fail, ok
from app.models import User
from products.contract.application.services import CustomerApplicationService
from products.contract.schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["contract-customers"])


def _response(customer) -> dict:
    return CustomerResponse.model_validate(customer).model_dump(mode="json")


@router.post("")
async def create_customer(
    body: CustomerCreate,
    user: User = Depends(require_user),
    service: CustomerApplicationService = Depends(get_customer_service),
):
    try:
        customer = await service.create(user_id=user.user_id, name=body.name, email=body.email)
    except ValueError as exc:
        return fail(str(exc), status_code=400)
    return ok("客户创建成功", _response(customer))


@router.get("")
async def list_customers(
    user: User = Depends(require_user),
    service: CustomerApplicationService = Depends(get_customer_service),
):
    return ok("获取客户成功", {"customers": [_response(item) for item in await service.list(user_id=user.user_id)]})


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int,
    user: User = Depends(require_user),
    service: CustomerApplicationService = Depends(get_customer_service),
):
    try:
        customer = await service.get(user_id=user.user_id, customer_id=customer_id)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    return ok("获取客户成功", _response(customer))


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    user: User = Depends(require_user),
    service: CustomerApplicationService = Depends(get_customer_service),
):
    try:
        customer = await service.update(user_id=user.user_id, customer_id=customer_id, name=body.name, email=body.email)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    except ValueError as exc:
        return fail(str(exc), status_code=400)
    return ok("客户更新成功", _response(customer))


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    user: User = Depends(require_user),
    service: CustomerApplicationService = Depends(get_customer_service),
):
    try:
        await service.delete(user_id=user.user_id, customer_id=customer_id)
    except LookupError as exc:
        return fail(str(exc), status_code=404)
    return ok("客户删除成功")
