from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.db.models.review import (
    ContractClauseModel,
    ContractReviewSelectionModel,
    ContractRiskModel,
    ContractVersionContentModel,
)
from products.contract.domain.review import ReviewContext, VersionContent
from products.contract.schemas.analysis import ContractAnalysis


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SqlAlchemyContractReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def claim(self, run_id: UUID) -> ReviewContext | None:
        claimed = await self.session.scalar(
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
            await self.session.rollback()
            return None
        await self.session.commit()

        run = await self.session.get(AnalysisRunModel, run_id)
        if run is None:
            return None
        version = await self.session.get(ContractVersionModel, run.version_id)
        if version is None:
            raise ValueError("合同版本不存在")
        version.status = "parsing"
        await self.session.commit()
        return ReviewContext(
            run_id=run.id,
            version_id=version.id,
            source_key=version.source_key,
            filename=version.filename,
        )

    async def get_content(self, version_id: UUID) -> VersionContent | None:
        model = await self.session.get(ContractVersionContentModel, version_id)
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

    async def save_content(self, content: VersionContent) -> None:
        self.session.add(
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
        await self.session.commit()

    async def mark_parsing(self, context: ReviewContext) -> None:
        run = await self.session.get(AnalysisRunModel, context.run_id)
        if run is None:
            raise ValueError("合同分析任务不存在")
        run.current_step = "parse_document"
        await self.session.commit()

    async def mark_analyzing(self, context: ReviewContext) -> None:
        run = await self.session.get(AnalysisRunModel, context.run_id)
        version = await self.session.get(ContractVersionModel, context.version_id)
        if run is None or version is None:
            raise ValueError("合同分析任务不存在")
        run.status = "analyzing"
        run.current_step = "analyze_contract"
        version.status = "analyzing"
        await self.session.commit()

    async def complete(
        self,
        context: ReviewContext,
        result: ContractAnalysis,
    ) -> None:
        run = await self.session.get(AnalysisRunModel, context.run_id)
        version = await self.session.get(ContractVersionModel, context.version_id)
        if run is None or version is None:
            raise ValueError("合同分析任务不存在")

        run.current_step = "persist_findings"
        await self.session.flush()
        await self.session.execute(
            delete(ContractRiskModel).where(ContractRiskModel.run_id == context.run_id)
        )
        await self.session.execute(
            delete(ContractClauseModel).where(ContractClauseModel.run_id == context.run_id)
        )

        clause_ids: dict[int, UUID] = {}
        for sequence, clause in enumerate(result.clauses, start=1):
            clause_id = uuid4()
            clause_ids[sequence] = clause_id
            self.session.add(
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
            self.session.add(
                ContractRiskModel(
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
        run.status = "completed"
        run.current_step = "review_required"
        run.error = None
        run.finished_at = _now()
        version.status = "completed"

        selection = pg_insert(ContractReviewSelectionModel).values(
            version_id=context.version_id,
            run_id=context.run_id,
        )
        await self.session.execute(
            selection.on_conflict_do_update(
                index_elements=[ContractReviewSelectionModel.version_id],
                set_={"run_id": context.run_id, "selected_at": _now()},
            )
        )
        await self.session.commit()

    async def fail(self, run_id: UUID, message: str) -> None:
        await self.session.rollback()
        run = await self.session.get(AnalysisRunModel, run_id)
        if run is None:
            return
        run.status = "failed"
        run.current_step = "failed"
        run.error = message
        run.finished_at = _now()
        version = await self.session.get(ContractVersionModel, run.version_id)
        if version is not None:
            version.status = "failed"
        await self.session.commit()
