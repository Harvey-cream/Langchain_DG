"""Contract Review 后台 Job Handler / composition root."""

from uuid import UUID

from app.db import SessionLocal
from infrastructure.db.repositories.contract_review_store import SqlAlchemyContractReviewStore
from infrastructure.document.contract_source import OssContractDocumentParser
from products.contract.agents.review_agent import LangChainContractReviewer
from products.contract.workflows.review_workflow import ContractReviewWorkflow

async def execute_analysis(run_id: UUID) -> None:
    async with SessionLocal() as db:
        workflow = ContractReviewWorkflow(
            db,
            SqlAlchemyContractReviewStore(db),
            OssContractDocumentParser(),
            LangChainContractReviewer(),
        )
        await workflow.run(run_id)
