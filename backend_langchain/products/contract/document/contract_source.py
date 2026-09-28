from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from common.storage import ObjectStoragePort
from products.contract.document.contract_parser import parse_contract
from common.storage.adapter import OssObjectStorage
from products.contract.domain.review import ReviewContext
from products.contract.domain.document import ParsedDocument


class OssContractDocumentParser:
    def __init__(self, storage: ObjectStoragePort | None = None) -> None:
        self.storage = storage or OssObjectStorage()

    async def parse(self, context: ReviewContext) -> ParsedDocument:
        def extract() -> ParsedDocument:
            with tempfile.TemporaryDirectory(prefix="contract-") as temp:
                path = Path(temp) / "original"
                self.storage.download(context.source_key, path)
                data = path.read_bytes()
                return parse_contract(context.filename, data, version_id=context.version_id)

        return await asyncio.to_thread(extract)
