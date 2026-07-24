"""企业知识库AI助手文档：OSS 直传 + 异步清洗入库。"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_db
from app.deps import require_user
from app.models import AgentDocument, User
from app.response import fail, ok
from app.settings import oss_config
from app.utils import format_datetime
from app.services.document_pipeline.ingest import detect_format
from app.services.oss_client import (
    OssNotConfiguredError,
    build_object_key,
    object_exists,
    sign_put_url,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent-documents"])

_ALLOWED_SUFFIX = frozenset({".md", ".markdown", ".pdf", ".txt", ".json"})


class UploadInitBody(BaseModel):
    filename: str = ""
    content_type: str = ""
    size_bytes: int = Field(default=0, ge=0)


def _safe_filename(name: str) -> str:
    base = Path(name or "").name.strip()
    return base.replace("\\", "_").replace("/", "_") or "file"


def _guess_content_type(filename: str, content_type: str) -> str:
    ct = (content_type or "").strip()
    if ct and ct != "application/octet-stream":
        return ct
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _doc_row(doc: AgentDocument) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "format": doc.format,
        "status": doc.status,
        "chunk_count": int(doc.chunk_count or 0),
        "size_bytes": int(doc.size_bytes or 0),
        "error_message": doc.error_message,
        "created_at": format_datetime(doc.created_at),
        "updated_at": format_datetime(doc.updated_at),
    }


async def _run_ingest(document_id: int) -> None:
    from app.services.document_pipeline.user_ingest import ingest_user_document_from_oss

    async with SessionLocal() as db:
        doc = await db.get(AgentDocument, document_id)
        if not doc:
            return
        doc.status = "processing"
        doc.error_message = None
        await db.commit()
        oss_key = doc.oss_key
        user_id = int(doc.user_id)
        filename = doc.filename
        fmt = doc.format

    try:
        chunk_count = await asyncio.to_thread(
            ingest_user_document_from_oss,
            oss_key=oss_key,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            fmt=fmt,
        )
        async with SessionLocal() as db:
            doc = await db.get(AgentDocument, document_id)
            if not doc:
                return
            doc.status = "ready"
            doc.chunk_count = chunk_count
            doc.error_message = None
            await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception("document ingest failed id=%s", document_id)
        async with SessionLocal() as db:
            doc = await db.get(AgentDocument, document_id)
            if not doc:
                return
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            await db.commit()


@router.post("/api/agent/documents/upload-init")
async def upload_init(
    body: UploadInitBody,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = oss_config()
    filename = _safe_filename(body.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIX:
        return fail("仅支持 .md / .pdf / .txt / .json", status_code=400)
    if body.size_bytes <= 0:
        return fail("文件大小无效", status_code=400)
    if body.size_bytes > int(cfg["max_file_bytes"]):
        mb = int(cfg["max_file_bytes"]) // (1024 * 1024)
        return fail(f"文件过大，上限 {mb}MB", status_code=400)

    content_type = _guess_content_type(filename, body.content_type)
    fmt = detect_format(Path(filename))

    doc = AgentDocument(
        user_id=user.user_id,
        filename=filename,
        format=fmt,
        content_type=content_type,
        size_bytes=int(body.size_bytes),
        status="pending",
        oss_key="",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    oss_key = build_object_key(user_id=user.user_id, document_id=doc.id, filename=filename)
    doc.oss_key = oss_key
    await db.commit()

    try:
        upload_url = sign_put_url(oss_key, content_type=content_type)
    except OssNotConfiguredError as e:
        await db.delete(doc)
        await db.commit()
        return fail(str(e), status_code=500)
    except Exception as e:  # noqa: BLE001
        logger.exception("sign_put_url failed")
        await db.delete(doc)
        await db.commit()
        return fail(f"生成上传地址失败: {e}", status_code=500)

    return ok(
        "上传凭证已生成",
        {
            "document_id": doc.id,
            "oss_key": oss_key,
            "upload_url": upload_url,
            "content_type": content_type,
            "expires_in": int(cfg["upload_url_expires"]),
        },
    )


@router.post("/api/agent/documents/{document_id}/confirm")
async def upload_confirm(
    document_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentDocument).where(
            AgentDocument.id == document_id,
            AgentDocument.user_id == user.user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return fail("文档不存在", status_code=404)
    if doc.status in ("processing", "ready"):
        return ok("文档已在处理或已入库", _doc_row(doc))

    try:
        if not object_exists(doc.oss_key):
            return fail("OSS 上未找到文件，请重新上传", status_code=400)
    except OssNotConfiguredError as e:
        return fail(str(e), status_code=500)
    except Exception as e:  # noqa: BLE001
        logger.exception("object_exists failed")
        return fail(f"校验 OSS 失败: {e}", status_code=500)

    doc.status = "pending"
    doc.error_message = None
    await db.commit()
    await db.refresh(doc)

    asyncio.create_task(_run_ingest(doc.id))
    return ok("已开始入库", _doc_row(doc))


@router.get("/api/agent/documents")
async def list_documents(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentDocument)
        .where(AgentDocument.user_id == user.user_id)
        .order_by(AgentDocument.created_at.desc())
    )
    rows = [_doc_row(d) for d in result.scalars()]
    return ok("获取文档列表成功", {"documents": rows})


@router.delete("/api/agent/documents/{document_id}")
async def delete_document(
    document_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.document_pipeline.user_ingest import purge_user_document

    result = await db.execute(
        select(AgentDocument).where(
            AgentDocument.id == document_id,
            AgentDocument.user_id == user.user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return fail("文档不存在", status_code=404)

    oss_key = doc.oss_key
    await db.delete(doc)
    await db.commit()

    await asyncio.to_thread(purge_user_document, document_id=document_id, oss_key=oss_key)
    return ok("删除成功")
