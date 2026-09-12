"""用户上传文档：OSS → 清洗切块 → pgvector（corpus=user，按 user_id 隔离）。"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from langchain_core.documents import Document

from app.services.document_pipeline.ingest import chunks_from_path, detect_format
from app.services.oss_client import delete_object, download_to_path
from infrastructure.rag.rag import get_store
from config.config import CORPUS_USER

logger = logging.getLogger(__name__)


def delete_document_vectors(document_id: int) -> int:
    return get_store().delete_by_document_id(document_id)


def ingest_user_document_from_oss(
    *,
    oss_key: str,
    user_id: int,
    document_id: int,
    filename: str,
    fmt: str | None = None,
) -> int:
    """同步：下载 → chunks_from_path → 写入 user_knowledge。返回 chunk 数。"""
    suffix = Path(filename).suffix.lower() or ".bin"
    tmp_root = Path(tempfile.mkdtemp(prefix=f"agent_doc_{document_id}_"))
    try:
        local = tmp_root / f"original{suffix}"
        download_to_path(oss_key, local)
        kind = fmt or detect_format(local)
        chunks = chunks_from_path(
            local,
            tmp_root,
            corpus=CORPUS_USER,
            domain=f"user_{user_id}",
            fmt=kind,
        )
        if not chunks:
            raise RuntimeError("清洗切块后无有效内容（空文件或无法抽取文本）")

        enriched: list[Document] = []
        for ch in chunks:
            meta = dict(ch.metadata or {})
            meta["corpus"] = CORPUS_USER
            meta["domain"] = f"user_{user_id}"
            meta["user_id"] = str(user_id)
            meta["document_id"] = str(document_id)
            meta["source_path"] = filename
            enriched.append(Document(page_content=ch.page_content, metadata=meta))

        return get_store().add(enriched)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def purge_user_document(*, document_id: int, oss_key: str) -> None:
    delete_document_vectors(document_id)
    try:
        delete_object(oss_key)
    except Exception:  # noqa: BLE001
        logger.exception("OSS 删除失败 document_id=%s key=%s", document_id, oss_key)
