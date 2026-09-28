"""One orchestration boundary for version facts; all external IO is outside transactions."""
from collections.abc import Sequence
from typing import Protocol

from products.contract import db as contract_db
from products.contract.domain.document import (
    INTELLIGENCE_VERSION,
    PARSER_VERSION,
    DocumentBlock,
    DocumentFacts,
    ParsedDocument,
)
from products.contract.domain.review import ReviewContext
from products.contract.schemas.document import ClauseExtraction, DocumentMetadata, SectionExtraction

from .clauses import extract_validated_candidates, ground_candidates
from .sections import block_windows, detect_sections
from .validation import validate_clauses


class ContractDocumentParser(Protocol):
    async def parse(self, context: ReviewContext) -> ParsedDocument: ...


class DocumentCapabilities(Protocol):
    async def sections(self, blocks: Sequence[DocumentBlock]) -> SectionExtraction: ...
    async def clauses(self, blocks: Sequence[DocumentBlock]) -> ClauseExtraction: ...
    async def metadata(self, blocks: Sequence[DocumentBlock]) -> DocumentMetadata: ...


class DocumentIntelligencePipeline:
    def __init__(self, session, parser: ContractDocumentParser,
                 capabilities: DocumentCapabilities):
        self.session, self.parser, self.capabilities = session, parser, capabilities

    async def ensure(self, context: ReviewContext) -> DocumentFacts:
        async with self.session.begin():
            existing = await contract_db.get_document_facts(
                self.session, context.version_id
            )
            if existing is not None:
                if (existing.document.parser_version != PARSER_VERSION
                        or existing.intelligence_version != INTELLIGENCE_VERSION):
                    raise ValueError("Document Facts 版本已变化，需要显式重新处理迁移")
                return existing
            parsed = await contract_db.get_parsed_document(
                self.session, context.version_id
            )

        if parsed is None:
            parsed = await self.parser.parse(context)
        if parsed.version_id != context.version_id or parsed.parser_version != PARSER_VERSION:
            raise ValueError("Parser 返回了错误的 Version 或 parser_version")
        sections = await detect_sections(parsed.blocks, self.capabilities.sections)
        by_id = {b.block_id: b for b in parsed.blocks}
        candidates = []
        for section in sections:
            blocks = tuple(by_id[key] for key in section.source_block_ids)
            candidates.extend(await extract_validated_candidates(context.version_id, blocks, self.capabilities.clauses))
        clauses = ground_candidates(context.version_id, parsed.blocks, candidates)
        coverage = validate_clauses(context.version_id, parsed.blocks, clauses)

        metadata_parts = []
        for window in block_windows(parsed.blocks):
            error = None
            for _ in range(2):
                try:
                    metadata_parts.append(DocumentMetadata.model_validate(await self.capabilities.metadata(window)))
                    break
                except ValueError as exc:
                    error = exc
            else:
                raise ValueError(f"Document Intelligence Metadata 校验失败: {error}") from error
        # Bounded per-window extraction, deterministic deduplication; no whole-document LLM merge.
        metadata = DocumentMetadata(
            **{key: '\n'.join(dict.fromkeys(getattr(part, key) for part in metadata_parts if getattr(part, key)))
               for key in ('summary', 'amount', 'duration', 'payment_terms')},
            parties=list(dict.fromkeys(party for part in metadata_parts for party in part.parties)),
        )
        facts = DocumentFacts(parsed, clauses, metadata.model_dump(mode="json"), coverage)
        # Publish content + blocks + canonical clauses + completion marker atomically.
        # A concurrent publisher wins once; the database function returns that fact set.
        async with self.session.begin():
            return await contract_db.save_document_facts(self.session, facts)
