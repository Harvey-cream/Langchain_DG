from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from products.contract.schemas.analysis import RiskLevel


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


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    our_party: str = Field(default="", max_length=255)
    party_role: str = Field(default="", max_length=64)
    contract_type: str = Field(default="", max_length=64)

    @field_validator("party_role", "contract_type")
    @classmethod
    def scope_value(cls, value: str) -> str:
        return value.strip().casefold()


class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="other", min_length=1, max_length=64)
    applicable_contract_types: list[str] = Field(default_factory=list, max_length=12)
    applicable_party_role: str = Field(default="", max_length=64)
    requirement: str = Field(min_length=1, max_length=2000)
    severity: RiskLevel
    enabled: bool = True

    @field_validator("name", "category", "requirement")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("规则字段不能为空白")
        return value.strip()

    @field_validator("applicable_party_role")
    @classmethod
    def party_scope(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("applicable_contract_types")
    @classmethod
    def contract_scope(cls, values: list[str]) -> list[str]:
        result = list(dict.fromkeys(v.strip().casefold() for v in values))
        if any(not v or len(v) > 64 for v in result):
            raise ValueError("合同类型必须是 1..64 字符")
        return result


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: str | None = None
    description: str | None = None
    category: str | None = None
    applicable_contract_types: list[str] | None = None
    applicable_party_role: str | None = None
    requirement: str | None = None
    severity: RiskLevel | None = None
    enabled: bool | None = None


class KnowledgeDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(min_length=1, max_length=64)
    expected_generation: int = Field(ge=1)

    @field_validator("category")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("文档分类不能为空白")
        return value.strip()


class KnowledgeSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=8000)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("检索问题不能为空白")
        return value.strip()
