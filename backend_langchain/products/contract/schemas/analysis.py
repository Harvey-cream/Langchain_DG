from typing import Literal
from pydantic import BaseModel, Field


class Risk(BaseModel):
    title: str
    risk_level: Literal['high', 'medium', 'low']
    original_text: str
    reason: str
    suggestion: str


class ContractAnalysis(BaseModel):
    document_type: str
    summary: str
    parties: list[str] = Field(default_factory=list)
    amount: str = ''
    duration: str = ''
    payment_terms: str = ''
    key_obligations: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
