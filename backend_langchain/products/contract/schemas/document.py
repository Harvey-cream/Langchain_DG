"""Structured outputs for document capabilities; never Review Agent schemas."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import get_args
from products.contract.schemas.analysis import ClauseType


class SectionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=255)
    source_block_ids: list[UUID] = Field(min_length=1)


class SectionExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[SectionCandidate] = Field(min_length=1)


class ClauseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    clause_type: str = "other"
    source_block_ids: list[UUID] = Field(min_length=1)

    @field_validator("clause_type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value if value in (*get_args(ClauseType), "unknown") else "other"


class ClauseExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clauses: list[ClauseCandidate] = Field(min_length=1)


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = ""
    parties: list[str] = Field(default_factory=list)
    amount: str = ""
    duration: str = ""
    payment_terms: str = ""
