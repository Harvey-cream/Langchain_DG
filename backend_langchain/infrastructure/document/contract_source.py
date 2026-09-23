from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

from app.services.oss_client import download_to_path
from infrastructure.document.contract_parser import parse_contract
from products.contract.domain.review import ReviewContext, VersionContent


class OssContractDocumentParser:
    async def parse(self, context: ReviewContext) -> VersionContent:
        def extract() -> VersionContent:
            with tempfile.TemporaryDirectory(prefix="contract-") as temp:
                path = Path(temp) / "original"
                download_to_path(context.source_key, path)
                data = path.read_bytes()
                text = parse_contract(context.filename, data)
                suffix = context.filename.lower().rsplit(".", 1)[-1]
                return VersionContent(
                    version_id=context.version_id,
                    document_text=text,
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    parser_name="pdfplumber" if suffix == "pdf" else "python-docx",
                )

        return await asyncio.to_thread(extract)
