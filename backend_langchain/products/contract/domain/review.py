from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReviewContext:
    run_id: UUID
    version_id: UUID
    source_key: str
    filename: str


@dataclass(frozen=True, slots=True)
class VersionContent:
    version_id: UUID
    document_text: str
    content_hash: str
    parser_name: str
    parser_version: str = "v1"
    page_count: int | None = None

    @property
    def character_count(self) -> int:
        return len(self.document_text)


@dataclass(frozen=True, slots=True)
class ReviewRunRecord:
    id: UUID
    version_id: UUID
    status: str
    current_step: str
    attempt: int
    result: dict[str, Any] | None
    error: str | None
    model_name: str | None
    prompt_version: str
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClauseRecord:
    id: UUID
    sequence: int
    clause_type: str
    title: str
    original_text: str
    summary: str
    locator: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RiskRecord:
    id: UUID
    clause_id: UUID | None
    title: str
    risk_level: str
    evidence_text: str
    reason: str
    suggestion: str
    review_status: str
    reviewer_note: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    latest_run: ReviewRunRecord | None
    selected_run: ReviewRunRecord | None
    document_text: str = ""
    clauses: list[ClauseRecord] = field(default_factory=list)
    risks: list[RiskRecord] = field(default_factory=list)
