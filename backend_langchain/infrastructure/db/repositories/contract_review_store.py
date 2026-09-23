from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import ContractModel, ContractVersionModel
from infrastructure.db.models.analysis import AnalysisRunModel
from infrastructure.db.models.review import (
    ContractClauseModel,
    ContractReviewSelectionModel,
    ContractRiskModel,
    ContractVersionContentModel,
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

ACTIVE_RUN_STATUSES = ("pending", "parsing", "analyzing")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SqlAlchemyContractReviewStore:
    """SQLAlchemy adapter for the Contract Review aggregate.

    This class deliberately never commits or rolls back. The application service and
    workflow own transaction boundaries.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_owned_contract(
        self, user_id: int, contract_id: UUID
    ) -> ContractModel | None:
        return await self.session.scalar(
            select(ContractModel).where(
                ContractModel.id == contract_id,
                ContractModel.user_id == user_id,
            )
        )

    async def lock_owned_contract(
        self, user_id: int, contract_id: UUID
    ) -> ContractModel | None:
        return await self.session.scalar(
            select(ContractModel)
            .where(
                ContractModel.id == contract_id,
                ContractModel.user_id == user_id,
            )
            .with_for_update()
        )

    async def get_owned_version(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ContractVersionModel | None:
        return await self.session.scalar(
            select(ContractVersionModel)
            .join(ContractModel, ContractModel.id == ContractVersionModel.contract_id)
            .where(
                ContractModel.user_id == user_id,
                ContractModel.id == contract_id,
                ContractVersionModel.id == version_id,
            )
        )

    async def lock_owned_version(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ContractVersionModel | None:
        return await self.session.scalar(
            select(ContractVersionModel)
            .join(ContractModel, ContractModel.id == ContractVersionModel.contract_id)
            .where(
                ContractModel.user_id == user_id,
                ContractModel.id == contract_id,
                ContractVersionModel.id == version_id,
            )
            .with_for_update()
        )

    async def get_next_version_number(self, contract_id: UUID) -> int:
        current = await self.session.scalar(
            select(func.max(ContractVersionModel.number)).where(
                ContractVersionModel.contract_id == contract_id
            )
        )
        return int(current or 0) + 1

    async def create_version(
        self,
        *,
        version_id: UUID,
        contract_id: UUID,
        number: int,
        source_key: str,
        filename: str,
        status: str,
    ) -> ContractVersionModel:
        version = ContractVersionModel(
            id=version_id,
            contract_id=contract_id,
            number=number,
            source_key=source_key,
            filename=filename,
            status=status,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_active_run(self, version_id: UUID) -> AnalysisRunModel | None:
        return await self.session.scalar(
            select(AnalysisRunModel).where(
                AnalysisRunModel.version_id == version_id,
                AnalysisRunModel.status.in_(ACTIVE_RUN_STATUSES),
            )
        )

    async def get_max_attempt(self, version_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(AnalysisRunModel.attempt)).where(
                AnalysisRunModel.version_id == version_id
            )
        )
        return int(value or 0)

    async def create_run(
        self,
        *,
        version_id: UUID,
        attempt: int,
        prompt_version: str = "v2",
    ) -> AnalysisRunModel:
        run = AnalysisRunModel(
            id=uuid4(),
            version_id=version_id,
            status="pending",
            current_step="queued",
            attempt=attempt,
            prompt_version=prompt_version,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def set_version_status(
        self, version: ContractVersionModel, status: str
    ) -> None:
        version.status = status

    async def claim_run(self, run_id: UUID) -> ReviewContext | None:
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
            return None

        run = await self.session.get(AnalysisRunModel, run_id)
        if run is None:
            return None
        version = await self.session.get(ContractVersionModel, run.version_id)
        if version is None:
            raise ValueError("合同版本不存在")
        version.status = "parsing"
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
        await self.session.flush()

    async def mark_parsing(self, context: ReviewContext) -> None:
        run = await self.session.get(AnalysisRunModel, context.run_id)
        if run is None:
            raise ValueError("合同分析任务不存在")
        run.current_step = "parse_document"

    async def mark_analyzing(self, context: ReviewContext) -> None:
        run = await self.session.get(AnalysisRunModel, context.run_id)
        version = await self.session.get(ContractVersionModel, context.version_id)
        if run is None or version is None:
            raise ValueError("合同分析任务不存在")
        run.status = "analyzing"
        run.current_step = "analyze_contract"
        version.status = "analyzing"

    async def complete_run(
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

    async def fail_run(self, run_id: UUID, message: str) -> None:
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

    async def load_snapshot(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ReviewSnapshot | None:
        if await self.get_owned_version(user_id, contract_id, version_id) is None:
            return None

        latest = await self.session.scalar(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.version_id == version_id)
            .order_by(AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc())
            .limit(1)
        )
        selected_id = await self.session.scalar(
            select(ContractReviewSelectionModel.run_id).where(
                ContractReviewSelectionModel.version_id == version_id
            )
        )
        selected = (
            await self.session.get(AnalysisRunModel, selected_id)
            if selected_id is not None
            else None
        )
        if selected is None:
            selected = await self.session.scalar(
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

        content = await self.session.get(ContractVersionContentModel, version_id)
        document_text = content.document_text if content is not None else ""
        clauses: list[ClauseRecord] = []
        risks: list[RiskRecord] = []
        if selected is not None:
            if not document_text:
                document_text = selected.document_text or ""
            clause_models = list(
                (
                    await self.session.scalars(
                        select(ContractClauseModel)
                        .where(ContractClauseModel.run_id == selected.id)
                        .order_by(ContractClauseModel.sequence)
                    )
                ).all()
            )
            risk_models = list(
                (
                    await self.session.scalars(
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
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> list[ReviewRunRecord] | None:
        if await self.get_owned_version(user_id, contract_id, version_id) is None:
            return None
        runs = list(
            (
                await self.session.scalars(
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
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
        run_id: UUID,
    ) -> bool:
        if await self.get_owned_version(user_id, contract_id, version_id) is None:
            return False
        run = await self.session.scalar(
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
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[ContractReviewSelectionModel.version_id],
                set_={"run_id": run_id, "selected_at": func.now()},
            )
        )
        return True


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
