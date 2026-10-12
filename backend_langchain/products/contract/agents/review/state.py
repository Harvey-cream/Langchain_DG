"""Review data in Graph state; clients and the per-invocation cache in Runtime."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Annotated, TYPE_CHECKING, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from products.contract.domain.document import CanonicalContractClause
from products.contract.schemas.analysis import ReviewResult, RiskFinding

if TYPE_CHECKING:
    from .llm import ReviewLLM


class ClauseInput(TypedDict):
    clause_id: str
    title: str
    clause_type: str
    original_text: str


class TargetClause(ClauseInput):
    sequence: int
    source_offset: int


class ReferenceSnapshot(TypedDict):
    chunk_id: str
    document_id: str
    document_version: int
    index_generation: int
    owner_id: int
    filename: str
    document_type: str
    chunk_text: str
    locator: dict
    embedding_model: str
    clause_ids: list[str]


class PolicySnapshot(TypedDict):
    id: str
    owner_id: int
    version: int
    name: str
    description: str
    category: str
    requirement: str
    severity: str
    enabled: bool
    archived: bool
    applicable_party_role: str
    applicable_contract_types: list[str]


class ReviewWindow(TypedDict):
    our_party: str
    business_scene: dict[str, str]
    metadata: dict
    policies: list[dict]
    targets: list[TargetClause]
    context_clauses: list[ClauseInput]
    references: list[dict]


class RetrievalEvent(TypedDict, total=False):
    kind: str
    query: str
    clause_ids: list[str]
    reference_count: int
    unavailable_count: int
    cache_hit: bool
    elapsed_seconds: float


class ReviewState(TypedDict):
    version_id: UUID
    user_id: int | None
    our_party: str
    party_role: str
    contract_type: str
    clauses: tuple[CanonicalContractClause, ...]
    metadata: dict
    policies: list[PolicySnapshot]
    windows: list[ReviewWindow]
    window_index: int
    current_window: ReviewWindow
    current_references: list[ReferenceSnapshot]
    messages: Annotated[list[BaseMessage], add_messages]
    tool_rounds: int
    tool_count: int
    processed_tool_ids: list[str]
    tools_pending: bool
    findings: list[RiskFinding]
    used_references: list[ReferenceSnapshot]
    retrieval_events: list[RetrievalEvent]
    result: ReviewResult
    quality_report: dict


@dataclass(frozen=True)
class ReviewLimits:
    react_enabled: bool = True
    max_tool_rounds: int = 2
    max_tool_calls: int = 4
    tool_timeout: float = 30
    model_timeout: float = 90
    recursion_limit: int = 512

    def __post_init__(self):
        if not 0 <= self.max_tool_rounds <= 4 or not 0 <= self.max_tool_calls <= 8:
            raise ValueError("Review 工具轮数允许 0–4，调用数量允许 0–8")
        if not 0 < self.tool_timeout <= 120 or not 0 < self.model_timeout <= 180:
            raise ValueError("Review 工具/模型超时配置不合法")
        if not 5 <= self.recursion_limit <= 2000:
            raise ValueError("Review recursion_limit 允许 5–2000")

    @classmethod
    def from_env(cls):
        enabled = os.getenv("CONTRACT_REVIEW_REACT_ENABLED", "true").casefold()
        if enabled not in ("true", "false", "1", "0"):
            raise ValueError("CONTRACT_REVIEW_REACT_ENABLED 必须为 true/false")
        return cls(
            react_enabled=enabled in ("true", "1"),
            max_tool_rounds=int(os.getenv("CONTRACT_REVIEW_MAX_TOOL_ROUNDS", "2")),
            max_tool_calls=int(os.getenv("CONTRACT_REVIEW_MAX_TOOL_CALLS", "4")),
            tool_timeout=float(os.getenv("CONTRACT_REVIEW_TOOL_TIMEOUT", "30")),
        )


@dataclass
class ReviewRuntime:
    """Created afresh for every review, never stored in Graph state or PostgreSQL."""

    llm: ReviewLLM
    limits: ReviewLimits
    retrieval_factory: async_sessionmaker[AsyncSession] | None
    trace: dict
    query_cache: dict[str, tuple[list[ReferenceSnapshot], dict]] = field(
        default_factory=dict
    )
    query_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass(frozen=True)
class ReviewGraphResult:
    result: ReviewResult
    used_references: list[ReferenceSnapshot] = field(default_factory=list)
    retrieval_events: list[RetrievalEvent] = field(default_factory=list)
    review_trace: dict = field(default_factory=dict)
    quality_report: dict = field(default_factory=dict)
    # Retain pre-dedupe findings so the authoritative DB gate keeps the original audit.
    raw_findings: list[RiskFinding] | None = None

    @property
    def risks(self) -> list[RiskFinding]:
        return self.result.risks

    @property
    def publication_result(self) -> ReviewResult:
        return (
            self.result
            if self.raw_findings is None
            else ReviewResult(risks=self.raw_findings)
        )
