from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)


class CustomerUpdate(CustomerCreate):
    pass


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContractCreate(BaseModel):
    customer_id: int
    title: str = Field(min_length=1, max_length=255)


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: int
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContractVersionCreate(BaseModel):
    source_key: str = Field(min_length=1, max_length=1024)
    filename: str = Field(min_length=1, max_length=512)


class ContractVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    contract_id: UUID
    number: int
    source_key: str
    filename: str
    status: str
    created_at: datetime | None = None
