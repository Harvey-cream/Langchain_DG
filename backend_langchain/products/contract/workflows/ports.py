from __future__ import annotations

from typing import Protocol
from products.contract.domain.review import ReviewContext, VersionContent
from products.contract.schemas.analysis import ContractAnalysis


class ContractDocumentParser(Protocol):
    async def parse(self, context: ReviewContext) -> VersionContent: ...


class ContractReviewer(Protocol):
    async def review(self, document_text: str) -> ContractAnalysis: ...
