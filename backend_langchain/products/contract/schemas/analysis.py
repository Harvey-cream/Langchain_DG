from collections.abc import Sequence
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from products.contract.domain.document import CanonicalContractClause

RiskLevel = Literal["high", "medium", "low"]


ClauseType = Literal[
    "parties",
    "subject",
    "amount",
    "payment",
    "delivery",
    "acceptance",
    "term",
    "termination",
    "breach",
    "confidentiality",
    "intellectual_property",
    "dispute",
    "other",
]


class Clause(BaseModel):
    clause_type: ClauseType = "other"
    title: str
    original_text: str
    summary: str = ""


class Risk(BaseModel):
    title: str
    risk_level: RiskLevel
    original_text: str
    reason: str
    suggestion: str
    clause_sequence: int | None = None


class ContractAnalysis(BaseModel):
    document_type: str
    summary: str
    parties: list[str] = Field(default_factory=list)
    amount: str = ""
    duration: str = ""
    payment_terms: str = ""
    key_obligations: list[str] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)


class ReferenceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: UUID
    source_excerpt: str = Field(min_length=1, max_length=1200)

    @field_validator("source_excerpt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("引用片段不能为空白")
        return value


class RiskFinding(BaseModel):
    """Run-owned judgement; clause_id always identifies a Version-owned clause."""

    model_config = ConfigDict(extra="forbid")
    clause_id: UUID
    risk_type: str = Field(min_length=1, max_length=64)
    risk_level: RiskLevel
    evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    related_clause_ids: list[UUID] = Field(default_factory=list, max_length=8)
    policy_ids: list[UUID] = Field(default_factory=list, max_length=12)
    reference_citations: list[ReferenceCitation] = Field(
        default_factory=list, max_length=8
    )

    @field_validator("risk_type", "evidence", "reason", "recommendation")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("风险字段不能为空白")
        return value


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risks: list[RiskFinding] = Field(default_factory=list)


def validate_findings(
    result: ReviewResult,
    clauses: Sequence[CanonicalContractClause],
    version_id: UUID,
    *,
    policies: Sequence[dict] = (),
    references: Sequence[dict] = (),
) -> ReviewResult:
    result = ReviewResult.model_validate(result)
    by_id = {clause.id: clause for clause in clauses}
    policy_by_id = {str(p["id"]): p for p in policies}
    reference_by_id = {str(r["chunk_id"]): r for r in references}
    if len(by_id) != len(clauses) or any(c.version_id != version_id for c in clauses):
        raise ValueError("审查条款重复或跨 Version")
    for risk in result.risks:
        seen_references = set()
        for citation in risk.reference_citations:
            reference = reference_by_id.get(str(citation.chunk_id))
            if (
                reference is None
                or citation.chunk_id in seen_references
                or citation.source_excerpt not in reference["chunk_text"]
                or str(risk.clause_id) not in reference.get("clause_ids", [])
            ):
                raise ValueError("RiskFinding 引用了未召回、跨条款或伪造的知识库资料")
            seen_references.add(citation.chunk_id)
        if len(set(risk.policy_ids)) != len(risk.policy_ids) or any(
            str(key) not in policy_by_id for key in risk.policy_ids
        ):
            raise ValueError("RiskFinding 引用了未提供或重复的企业规则")
        levels = {"low": 0, "medium": 1, "high": 2}
        if any(
            levels[risk.risk_level] < levels[policy_by_id[str(key)]["severity"]]
            for key in risk.policy_ids
        ):
            raise ValueError("风险等级不能低于所引用企业规则的等级")
        clause = by_id.get(risk.clause_id)
        if clause is None:
            raise ValueError("RiskFinding 引用了不存在或跨版本的 Canonical Clause")
        if risk.evidence not in clause.original_text:
            raise ValueError("RiskFinding 证据不在关联条款的真实原文中")
        if (
            len(set(risk.related_clause_ids)) != len(risk.related_clause_ids)
            or risk.clause_id in risk.related_clause_ids
            or any(key not in by_id for key in risk.related_clause_ids)
        ):
            raise ValueError("RiskFinding 相关条款重复、不存在或跨版本")
    return result
