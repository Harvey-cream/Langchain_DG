"""Version-owned document facts, independent of Review V1 outputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

PARSER_VERSION = "v2"
INTELLIGENCE_VERSION = "v1"
BLOCK_JOIN = "\n\n"
BlockType = Literal["heading", "paragraph", "table", "unknown"]


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    block_id: UUID
    version_id: UUID
    sequence: int
    text: str
    type: BlockType = "paragraph"
    page: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    version_id: UUID
    document_text: str
    blocks: tuple[DocumentBlock, ...]
    page_count: int | None
    parser_name: str
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True, slots=True)
class DocumentSection:
    title: str
    source_block_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CanonicalContractClause:
    id: UUID
    version_id: UUID
    sequence: int
    title: str
    clause_type: str
    original_text: str
    source_block_ids: tuple[UUID, ...]
    pages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CoverageReport:
    covered_meaningful_blocks: int
    total_meaningful_blocks: int
    ratio: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    document: ParsedDocument
    clauses: tuple[CanonicalContractClause, ...]
    metadata: dict
    coverage: CoverageReport
    intelligence_version: str = INTELLIGENCE_VERSION
