from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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
    ReviewRunRecord,
    ReviewSnapshot,
    RiskRecord,
)


class SqlAlchemyContractReviewQueryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _owned_version(
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

    async def load_snapshot(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> ReviewSnapshot | None:
        if await self._owned_version(user_id, contract_id, version_id) is None:
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
                .order_by(AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc())
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

    async def list_runs(
        self,
        user_id: int,
        contract_id: UUID,
        version_id: UUID,
    ) -> list[ReviewRunRecord] | None:
        if await self._owned_version(user_id, contract_id, version_id) is None:
            return None
        runs = list(
            (
                await self.session.scalars(
                    select(AnalysisRunModel)
                    .where(AnalysisRunModel.version_id == version_id)
                    .order_by(AnalysisRunModel.created_at.desc(), AnalysisRunModel.id.desc())
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
        if await self._owned_version(user_id, contract_id, version_id) is None:
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
        await self.session.commit()
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
