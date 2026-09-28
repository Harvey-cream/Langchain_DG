"""Contract Review 后台 Job Handler / composition root."""

from uuid import UUID

from common.database import SessionLocal
from products.contract.document.contract_source import OssContractDocumentParser
from products.contract.document.contract_intelligence import LangChainDocumentIntelligence
from products.contract.document_intelligence.pipeline import DocumentIntelligencePipeline
from products.contract.agents.review_agent import LangChainContractReviewer
from products.contract.workflows.review_workflow import run_contract_review

async def execute_analysis(run_id: UUID) -> None:
    async with SessionLocal() as db:
        pipeline = DocumentIntelligencePipeline(
            db,
            OssContractDocumentParser(),
            LangChainDocumentIntelligence(),
        )
        await run_contract_review(db, pipeline, LangChainContractReviewer(), run_id)
