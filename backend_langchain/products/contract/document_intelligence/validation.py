"""Deterministic grounding checks; coverage diagnoses omissions without a hard gate."""
from collections.abc import Sequence
from uuid import UUID

from products.contract.domain.document import (
    BLOCK_JOIN, CanonicalContractClause, CoverageReport, DocumentBlock,
)


def validate_clauses(
    version_id: UUID, blocks: Sequence[DocumentBlock], clauses: Sequence[CanonicalContractClause],
) -> CoverageReport:
    if not blocks or not clauses:
        raise ValueError("Document Intelligence 文档或 Clause 为空")
    by_id = {b.block_id: b for b in blocks}
    sequences = [b.sequence for b in blocks]
    if (len(by_id) != len(blocks) or sequences != sorted(set(sequences))
            or any(b.sequence < 1 or b.version_id != version_id for b in blocks)):
        raise ValueError("DocumentBlock 标识、顺序或 Version 非法")
    if [c.sequence for c in clauses] != list(range(1, len(clauses) + 1)):
        raise ValueError("Canonical Clause sequence 非法")
    seen, previous_start = set(), 0
    for clause in clauses:
        ids = clause.source_block_ids
        if clause.version_id != version_id:
            raise ValueError("Canonical Clause 跨 Version")
        if not ids or not clause.original_text.strip():
            raise ValueError("Canonical Clause 为空")
        if len(set(ids)) != len(ids) or seen.intersection(ids):
            raise ValueError("Block 被 Clause 重复引用")
        if any(key not in by_id for key in ids):
            raise ValueError("Clause 引用了不存在的 Block")
        resolved = [by_id[key] for key in ids]
        positions = [b.sequence for b in resolved]
        if positions != sorted(positions) or positions[0] < previous_start:
            raise ValueError("Clause Block 顺序异常")
        previous_start = positions[0]
        if clause.original_text != BLOCK_JOIN.join(b.text for b in resolved):
            raise ValueError("Clause original_text 与来源 Block 不完全一致")
        if clause.pages != tuple(sorted({b.page for b in resolved if b.page is not None})):
            raise ValueError("Clause 页码与来源 Block 不一致")
        seen.update(ids)
    # Includes titles and tables that contain any letter/number (including Chinese).
    meaningful = {b.block_id for b in blocks if any(char.isalnum() for char in b.text)}
    covered = len(meaningful & seen)
    total = len(meaningful)
    ratio = covered / total if total else 1.0
    warnings = (f"Document coverage incomplete: {covered}/{total} meaningful blocks",) if covered < total else ()
    return CoverageReport(covered, total, ratio, warnings)
