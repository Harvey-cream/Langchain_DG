from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID, uuid5

from products.contract.domain.document import (
    BLOCK_JOIN, INTELLIGENCE_VERSION, CanonicalContractClause, DocumentBlock,
)
from products.contract.schemas.document import ClauseCandidate, ClauseExtraction


def source_blocks(candidate: ClauseCandidate, blocks: Sequence[DocumentBlock]) -> tuple[DocumentBlock, ...]:
    """Resolve references strictly. Never silently discard an invalid LLM ID."""
    by_id = {b.block_id: b for b in blocks}
    ids = candidate.source_block_ids
    if len(set(ids)) != len(ids):
        raise ValueError("Clause 重复引用 Block")
    if any(key not in by_id for key in ids):
        raise ValueError("Clause 引用了不存在的 Block")
    resolved = tuple(by_id[key] for key in ids)
    sequences = [b.sequence for b in resolved]
    if sequences != sorted(sequences):
        raise ValueError("Clause Block 顺序异常")
    if not resolved or not any(b.text.strip() for b in resolved):
        raise ValueError("Clause 为空")
    return resolved


async def extract_candidates(
    blocks: Sequence[DocumentBlock],
    extract: Callable[[Sequence[DocumentBlock]], Awaitable[ClauseExtraction]],
) -> tuple[ClauseCandidate, ...]:
    result = ClauseExtraction.model_validate(await extract(blocks))
    for candidate in result.clauses:
        source_blocks(candidate, blocks)
    return tuple(result.clauses)


def ground_candidates(
    version_id: UUID, blocks: Sequence[DocumentBlock], candidates: Sequence[ClauseCandidate],
) -> tuple[CanonicalContractClause, ...]:
    clauses = []
    for sequence, candidate in enumerate(candidates, 1):
        resolved = sorted(source_blocks(candidate, blocks), key=lambda b: b.sequence)
        if any(b.version_id != version_id for b in resolved):
            raise ValueError("Clause 引用了跨 Version 的 Block")
        ids = tuple(b.block_id for b in resolved)
        clauses.append(CanonicalContractClause(
            id=uuid5(version_id, f"{INTELLIGENCE_VERSION}:{sequence}:" + ','.join(map(str, ids))),
            version_id=version_id, sequence=sequence, title=candidate.title,
            clause_type=candidate.clause_type,
            original_text=BLOCK_JOIN.join(b.text for b in resolved),
            source_block_ids=ids,
            pages=tuple(sorted({b.page for b in resolved if b.page is not None})),
        ))
    return tuple(clauses)


async def extract_validated_candidates(version_id, blocks, extract) -> tuple[ClauseCandidate, ...]:
    from products.contract.document_intelligence.validation import validate_clauses

    error = None
    for _ in range(2):  # Same bounded-attempt style as Review V1 evidence validation.
        try:
            candidates = await extract_candidates(blocks, extract)
            validate_clauses(version_id, blocks, ground_candidates(version_id, blocks, candidates))
            return candidates
        except ValueError as exc:
            error = exc
    raise ValueError(f"Document Intelligence Clause 校验失败: {error}") from error
