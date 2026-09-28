"""Complex Contract review and document persistence.

HTTP-only CRUD lives beside its FastAPI endpoints. This module keeps only the
transactional operations shared by background review and document intelligence.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from products.contract.models import (
    AnalysisRunModel,
    CanonicalContractClauseModel,
    ContractClauseModel,
    ContractDocumentBlockModel,
    ContractDocumentFactsModel,
    ContractModel,
    ContractReviewSelectionModel,
    ContractRiskModel,
    ContractVersionContentModel,
    ContractVersionModel,
)
from products.contract.document_intelligence.validation import validate_clauses
from products.contract.domain.document import (
    CanonicalContractClause,
    DocumentBlock,
    DocumentFacts,
    ParsedDocument,
)
from products.contract.domain.review import (
    ClauseRecord,
    ReviewContext,
    ReviewRunRecord,
    ReviewSnapshot,
    RiskRecord,
    VersionContent,
)
from products.contract.schemas.analysis import ContractAnalysis
from products.contract.schemas.document import DocumentMetadata


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _get_owned_version(
    session: AsyncSession,
    user_id: int,
    contract_id: UUID,
    version_id: UUID,
) -> ContractVersionModel | None:
    return await session.scalar(
        select(ContractVersionModel)
        .join(ContractModel, ContractModel.id == ContractVersionModel.contract_id)
        .where(
            ContractModel.user_id == user_id,
            ContractModel.id == contract_id,
            ContractVersionModel.id == version_id,
        )
    )

# Background review execution.
async def claim_run(session: AsyncSession, run_id: UUID) -> ReviewContext | None:
    claimed = await session.scalar(
        update(AnalysisRunModel)
        .where(
            AnalysisRunModel.id == run_id,
            AnalysisRunModel.status == "pending",
        )
        .values(
            status="parsing",
            current_step="load_content",
            started_at=_now(),
            error=None,
            finished_at=None,
        )
        .returning(AnalysisRunModel.id)
    )
    if claimed is None:
        return None

    run = await session.get(AnalysisRunModel, run_id)
    if run is None:
        return None
    version = await session.get(ContractVersionModel, run.version_id)
    if version is None:
        raise ValueError("合同版本不存在")
    version.status = "parsing"
    return ReviewContext(
        run_id=run.id,
        version_id=version.id,
        source_key=version.source_key,
        filename=version.filename,
    )

async def get_content(session: AsyncSession, version_id: UUID) -> VersionContent | None:
    model = await session.get(ContractVersionContentModel, version_id)
    if model is None:
        return None
    return VersionContent(
        version_id=model.version_id,
        document_text=model.document_text,
        content_hash=model.content_hash,
        parser_name=model.parser_name,
        parser_version=model.parser_version,
        page_count=model.page_count,
    )

async def save_content(session: AsyncSession, content: VersionContent) -> None:
    session.add(
        ContractVersionContentModel(
            version_id=content.version_id,
            document_text=content.document_text,
            content_hash=content.content_hash,
            parser_name=content.parser_name,
            parser_version=content.parser_version,
            page_count=content.page_count,
            character_count=content.character_count,
        )
    )
    await session.flush()

async def mark_parsing(session: AsyncSession, context: ReviewContext) -> None:
    run = await session.get(AnalysisRunModel, context.run_id)
    if run is None:
        raise ValueError("合同分析任务不存在")
    run.current_step = "parse_document"


# Parsed source content and canonical document facts.
async def get_parsed_document(session: AsyncSession, version_id: UUID) -> ParsedDocument | None:
    content = await get_content(session, version_id)
    rows = (await session.scalars(
        select(ContractDocumentBlockModel)
        .where(ContractDocumentBlockModel.version_id == version_id)
        .order_by(ContractDocumentBlockModel.sequence)
    )).all()
    if content is None or not rows:
        return None
    return ParsedDocument(
        version_id, content.document_text,
        tuple(DocumentBlock(r.id, r.version_id, r.sequence, r.text, r.type, r.page) for r in rows),
        content.page_count, content.parser_name, content.parser_version,
    )

async def save_parsed_document(session: AsyncSession, document: ParsedDocument) -> None:
    # Caller owns the transaction; Version row serializes concurrent publishers.
    version = await session.scalar(select(ContractVersionModel).where(
        ContractVersionModel.id == document.version_id).with_for_update())
    if version is None:
        raise ValueError("合同版本不存在")
    blocks = document.blocks
    if (not blocks or not any(b.text.strip() for b in blocks)
            or any(b.version_id != document.version_id or not b.text for b in blocks)
            or [b.sequence for b in blocks] != list(range(1, len(blocks) + 1))
            or len({b.block_id for b in blocks}) != len(blocks)):
        raise ValueError("DocumentBlock 版本、顺序、标识或正文非法")
    existing = await get_parsed_document(session, document.version_id)
    if existing is not None:
        if existing != document:
            raise ValueError("已发布的文档 Blocks 不可隐式替换，请使用显式版本迁移")
        return
    content = VersionContent.from_parsed(document)
    model = await session.get(ContractVersionContentModel, document.version_id)
    if model is None:
        await save_content(session, content)
    else:
        # Lazy reparse of legacy text; no inference from legacy Run clauses.
        # Preserve the exact source shown with older successful review results.
        await session.execute(update(AnalysisRunModel).where(
            AnalysisRunModel.version_id == document.version_id,
            AnalysisRunModel.status == "completed",
            (AnalysisRunModel.document_text.is_(None) | (AnalysisRunModel.document_text == "")),
        ).values(document_text=model.document_text))
        for key in ("document_text", "content_hash", "parser_name", "parser_version", "page_count", "character_count"):
            setattr(model, key, getattr(content, key))
    session.add_all([
        ContractDocumentBlockModel(id=b.block_id, version_id=b.version_id,
            sequence=b.sequence, text=b.text, type=b.type, page=b.page)
        for b in blocks
    ])
    await session.flush()

async def mark_analyzing(session: AsyncSession, context: ReviewContext) -> None:
    run = await session.get(AnalysisRunModel, context.run_id)
    version = await session.get(ContractVersionModel, context.version_id)
    if run is None or version is None:
        raise ValueError("合同分析任务不存在")
    run.status = "analyzing"
    run.current_step = "analyze_contract"
    version.status = "analyzing"

async def get_canonical_clauses(session: AsyncSession, version_id: UUID) -> tuple[CanonicalContractClause, ...]:
    rows = (await session.scalars(select(CanonicalContractClauseModel)
        .where(CanonicalContractClauseModel.version_id == version_id)
        .order_by(CanonicalContractClauseModel.sequence))).all()
    return tuple(CanonicalContractClause(
        r.id, r.version_id, r.sequence, r.title, r.clause_type, r.original_text,
        tuple(UUID(key) for key in r.source_block_ids), tuple(r.pages),
    ) for r in rows)

async def save_canonical_clauses(
    session: AsyncSession, version_id: UUID, clauses: tuple[CanonicalContractClause, ...], intelligence_version: str,
) -> None:
    await session.scalar(select(ContractVersionModel)
        .where(ContractVersionModel.id == version_id).with_for_update())
    parsed = await get_parsed_document(session, version_id)
    if parsed is None:
        raise ValueError("Canonical Clause 缺少持久化的来源 Block")
    # JSONB references are validated against the actual rows before any insert.
    validate_clauses(version_id, parsed.blocks, clauses)
    existing = await get_canonical_clauses(session, version_id)
    if existing:
        versions = (await session.scalars(select(CanonicalContractClauseModel.intelligence_version)
            .where(CanonicalContractClauseModel.version_id == version_id))).all()
        if existing != clauses or any(v != intelligence_version for v in versions):
            raise ValueError("已发布 Canonical Clauses 不可隐式替换，请使用显式版本迁移")
        return
    session.add_all([CanonicalContractClauseModel(
        id=c.id, version_id=c.version_id, sequence=c.sequence, title=c.title,
        clause_type=c.clause_type, original_text=c.original_text,
        source_block_ids=[str(key) for key in c.source_block_ids], pages=list(c.pages),
        intelligence_version=intelligence_version,
    ) for c in clauses])
    await session.flush()


# Review result persistence and history selection.
async def complete_run(
    session: AsyncSession,
    context: ReviewContext,
    result: ContractAnalysis,
) -> None:
    run = await session.get(AnalysisRunModel, context.run_id)
    version = await session.get(ContractVersionModel, context.version_id)
    if run is None or version is None:
        raise ValueError("合同分析任务不存在")

    run.current_step = "persist_findings"
    await session.flush()
    await session.execute(
        delete(ContractRiskModel).where(ContractRiskModel.run_id == context.run_id)
    )
    await session.execute(
        delete(ContractClauseModel).where(ContractClauseModel.run_id == context.run_id)
    )

    clause_ids: dict[int, UUID] = {}
    for sequence, clause in enumerate(result.clauses, start=1):
        clause_id = uuid4()
        clause_ids[sequence] = clause_id
        session.add(
            ContractClauseModel(
                id=clause_id,
                version_id=context.version_id,
                run_id=context.run_id,
                sequence=sequence,
                clause_type=clause.clause_type,
                title=clause.title,
                original_text=clause.original_text,
                summary=clause.summary,
            )
        )

    for risk in result.risks:
        session.add(
            ContractRiskModel(
                id=uuid4(),
                version_id=context.version_id,
                run_id=context.run_id,
                clause_id=clause_ids.get(risk.clause_sequence),
                title=risk.title,
                risk_level=risk.risk_level,
                evidence_text=risk.original_text,
                reason=risk.reason,
                suggestion=risk.suggestion,
                review_status="pending",
            )
        )

    run.result = result.model_dump(mode="json")
    content = await get_content(session, context.version_id)
    if content is not None:
        run.document_text = content.document_text
    run.status = "completed"
    run.current_step = "review_required"
    run.error = None
    run.finished_at = _now()
    version.status = "completed"

    selection = pg_insert(ContractReviewSelectionModel).values(
        version_id=context.version_id,
        run_id=context.run_id,
    )
    await session.execute(
        selection.on_conflict_do_update(
            index_elements=[ContractReviewSelectionModel.version_id],
            set_={"run_id": context.run_id, "selected_at": _now()},
        )
    )

async def fail_run(session: AsyncSession, run_id: UUID, message: str) -> None:
    run = await session.get(AnalysisRunModel, run_id)
    if run is None:
        return
    run.status = "failed"
    run.current_step = "failed"
    run.error = message
    run.finished_at = _now()
    version = await session.get(ContractVersionModel, run.version_id)
    if version is not None:
        version.status = "failed"

async def load_snapshot(
    session: AsyncSession,
    user_id: int,
    contract_id: UUID,
    version_id: UUID,
) -> ReviewSnapshot | None:
    if await _get_owned_version(session, user_id, contract_id, version_id) is None:
        return None

    latest = await session.scalar(
        select(AnalysisRunModel)
        .where(AnalysisRunModel.version_id == version_id)
        .order_by(AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc())
        .limit(1)
    )
    selected_id = await session.scalar(
        select(ContractReviewSelectionModel.run_id).where(
            ContractReviewSelectionModel.version_id == version_id
        )
    )
    selected = (
        await session.get(AnalysisRunModel, selected_id)
        if selected_id is not None
        else None
    )
    if selected is None:
        selected = await session.scalar(
            select(AnalysisRunModel)
            .where(
                AnalysisRunModel.version_id == version_id,
                AnalysisRunModel.status == "completed",
            )
            .order_by(
                AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc()
            )
            .limit(1)
        )

    content = await session.get(ContractVersionContentModel, version_id)
    document_text = content.document_text if content is not None else ""
    clauses: list[ClauseRecord] = []
    risks: list[RiskRecord] = []
    if selected is not None:
        if selected.document_text:
            document_text = selected.document_text
        clause_models = list(
            (
                await session.scalars(
                    select(ContractClauseModel)
                    .where(ContractClauseModel.run_id == selected.id)
                    .order_by(ContractClauseModel.sequence)
                )
            ).all()
        )
        risk_models = list(
            (
                await session.scalars(
                    select(ContractRiskModel)
                    .where(ContractRiskModel.run_id == selected.id)
                    .order_by(ContractRiskModel.created_at, ContractRiskModel.id)
                )
            ).all()
        )
        clauses = [_clause_record(item) for item in clause_models]
        risks = [_risk_record(item) for item in risk_models]

    return ReviewSnapshot(
        latest_run=_run_record(latest) if latest is not None else None,
        selected_run=_run_record(selected) if selected is not None else None,
        document_text=document_text,
        clauses=clauses,
        risks=risks,
    )

async def list_history(
    session: AsyncSession,
    user_id: int,
    contract_id: UUID,
    version_id: UUID,
) -> list[ReviewRunRecord] | None:
    if await _get_owned_version(session, user_id, contract_id, version_id) is None:
        return None
    runs = list(
        (
            await session.scalars(
                select(AnalysisRunModel)
                .where(AnalysisRunModel.version_id == version_id)
                .order_by(
                    AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc()
                )
            )
        ).all()
    )
    return [_run_record(run) for run in runs]

async def select_run(
    session: AsyncSession,
    user_id: int,
    contract_id: UUID,
    version_id: UUID,
    run_id: UUID,
) -> bool:
    if await _get_owned_version(session, user_id, contract_id, version_id) is None:
        return False
    run = await session.scalar(
        select(AnalysisRunModel).where(
            AnalysisRunModel.id == run_id,
            AnalysisRunModel.version_id == version_id,
            AnalysisRunModel.status == "completed",
            AnalysisRunModel.result.is_not(None),
        )
    )
    if run is None:
        return False
    statement = pg_insert(ContractReviewSelectionModel).values(
        version_id=version_id,
        run_id=run_id,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[ContractReviewSelectionModel.version_id],
            set_={"run_id": run_id, "selected_at": func.now()},
        )
    )
    return True


# Version-level Document Intelligence cache.
async def get_document_facts(session: AsyncSession, version_id: UUID) -> DocumentFacts | None:
    model = await session.get(ContractDocumentFactsModel, version_id)
    if model is None:
        return None
    parsed = await get_parsed_document(session, version_id)
    clauses = await get_canonical_clauses(session, version_id)
    if (parsed is None or parsed.parser_version != model.parser_version
            or VersionContent.from_parsed(parsed).content_hash != model.content_hash):
        raise ValueError("已发布 Document Facts 的正文或解析版本不一致")
    coverage = validate_clauses(version_id, parsed.blocks, clauses)
    if (coverage.covered_meaningful_blocks != model.covered_blocks
            or coverage.total_meaningful_blocks != model.total_blocks
            or coverage.ratio != model.coverage_ratio):
        raise ValueError("已发布 Document Facts 的 Coverage 不一致")
    clause_versions = (await session.scalars(select(CanonicalContractClauseModel.intelligence_version)
        .where(CanonicalContractClauseModel.version_id == version_id))).all()
    if any(value != model.intelligence_version for value in clause_versions):
        raise ValueError("Canonical Clause 的 intelligence_version 与 Facts 不一致")
    return DocumentFacts(parsed, clauses,
        DocumentMetadata.model_validate(model.extracted_metadata).model_dump(),
        coverage, model.intelligence_version)

async def save_document_facts(session: AsyncSession, facts: DocumentFacts) -> DocumentFacts:
    parsed = facts.document
    version = await session.scalar(select(ContractVersionModel)
        .where(ContractVersionModel.id == parsed.version_id).with_for_update())
    if version is None:
        raise ValueError("合同版本不存在")
    existing = await get_document_facts(session, parsed.version_id)
    if existing is not None:
        if (existing.document != parsed or existing.intelligence_version != facts.intelligence_version):
            raise ValueError("已发布的 Document Facts 不能隐式替换")
        return existing
    coverage = validate_clauses(parsed.version_id, parsed.blocks, facts.clauses)
    if coverage != facts.coverage:
        raise ValueError("Document Facts Coverage 与条款不一致")
    metadata = DocumentMetadata.model_validate(facts.metadata)
    await save_parsed_document(session, parsed)
    await save_canonical_clauses(session, parsed.version_id, facts.clauses, facts.intelligence_version)
    session.add(ContractDocumentFactsModel(
        version_id=parsed.version_id, parser_version=parsed.parser_version,
        intelligence_version=facts.intelligence_version,
        content_hash=VersionContent.from_parsed(parsed).content_hash,
        extracted_metadata=metadata.model_dump(mode="json"),
        covered_blocks=coverage.covered_meaningful_blocks,
        total_blocks=coverage.total_meaningful_blocks, coverage_ratio=coverage.ratio,
        warnings=list(coverage.warnings),
    ))
    await session.flush()
    return facts


def _run_record(model: AnalysisRunModel) -> ReviewRunRecord:
    return ReviewRunRecord(
        id=model.id,
        version_id=model.version_id,
        status=model.status,
        current_step=model.current_step,
        attempt=model.attempt,
        result=model.result,
        error=model.error,
        model_name=model.model_name,
        prompt_version=model.prompt_version,
        created_at=model.created_at,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


def _clause_record(model: ContractClauseModel) -> ClauseRecord:
    return ClauseRecord(
        id=model.id,
        sequence=model.sequence,
        clause_type=model.clause_type,
        title=model.title,
        original_text=model.original_text,
        summary=model.summary,
        locator=model.locator,
    )


def _risk_record(model: ContractRiskModel) -> RiskRecord:
    return RiskRecord(
        id=model.id,
        clause_id=model.clause_id,
        title=model.title,
        risk_level=model.risk_level,
        evidence_text=model.evidence_text,
        reason=model.reason,
        suggestion=model.suggestion,
        review_status=model.review_status,
        reviewer_note=model.reviewer_note,
    )
