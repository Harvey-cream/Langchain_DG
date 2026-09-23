from typing import Literal
from pydantic import BaseModel, Field


ClauseType = Literal[
    'parties',
    'subject',
    'amount',
    'payment',
    'delivery',
    'acceptance',
    'term',
    'termination',
    'breach',
    'confidentiality',
    'intellectual_property',
    'dispute',
    'other',
]


class Clause(BaseModel):
    clause_type: ClauseType = 'other'
    title: str
    original_text: str
    summary: str = ''


class Risk(BaseModel):
    title: str
    risk_level: Literal['high', 'medium', 'low']
    original_text: str
    reason: str
    suggestion: str
    clause_sequence: int | None = None


class ContractAnalysis(BaseModel):
    document_type: str
    summary: str
    parties: list[str] = Field(default_factory=list)
    amount: str = ''
    duration: str = ''
    payment_terms: str = ''
    key_obligations: list[str] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
