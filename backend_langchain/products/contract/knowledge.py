"""Reference ingestion jobs and lossless retrieval chunks, not ContractVersions."""

import asyncio
import hashlib
import tempfile
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy import delete, select, update
from common.database import SessionLocal
from common.storage.adapter import OssObjectStorage
from common.integrations.retrieval_models import make_dashscope_embeddings
from common.config.config import dashscope_model_name
from products.contract.document.contract_parser import parse_contract
from products.contract.domain.document import join_block_text
from products.contract.models import (
    ContractKnowledgeDocumentModel as Document,
    ContractKnowledgeChunkModel as Chunk,
)
from products.contract.retrieval import EMBEDDING_DIMENSIONS, tokenize, validate_vectors


def chunk_document(document, *, size=1200, overlap=150):
    if not 0 <= overlap < size:
        raise ValueError("Chunk overlap 必须小于 size")
    text = join_block_text(document.blocks)
    offsets, cursor, previous = [], 0, None
    for block in document.blocks:
        if previous is not None and not (
            block.join_previous and block.sequence == previous.sequence + 1
        ):
            cursor += 2
        offsets.append((cursor, cursor + len(block.text), block))
        cursor += len(block.text)
        previous = block
    result, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        source = [
            block for left, right, block in offsets if left < end and right > start
        ]
        value = text[start:end]
        if value.strip():
            result.append(
                dict(
                    sequence=len(result) + 1,
                    chunk_text=value,
                    locator=dict(
                        start_char=start,
                        end_char=end,
                        block_sequences=[block.sequence for block in source],
                        pages=sorted(
                            {block.page for block in source if block.page is not None}
                        ),
                    ),
                    token_index=tokenize(value),
                )
            )
        if end == len(text):
            break
        start = end - overlap
    if not result:
        raise ValueError("知识库文档没有可索引文本")
    return result


async def ingest_document(
    document_id: UUID,
    generation: int,
    *,
    factory=None,
    storage=None,
    embeddings=None,
    timeout=180,
):
    factory, storage = factory or SessionLocal, storage or OssObjectStorage()
    claimed = False
    try:
        async with factory() as session, session.begin():
            owned_id = await session.scalar(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.generation == generation,
                    Document.status == "uploaded",
                )
                .values(status="processing", error=None, attempt=Document.attempt + 1)
                .returning(Document.id)
            )
            if owned_id is None:
                return
            claimed = True
            model = await session.get(Document, document_id)
            filename, source_key, owner_id, document_version = (
                model.filename,
                model.source_key,
                model.user_id,
                model.document_version,
            )

        def parse():
            with tempfile.TemporaryDirectory(prefix="contract-knowledge-") as temp:
                target = Path(temp) / "original"
                storage.download(source_key, target)
                return parse_contract(
                    filename, target.read_bytes(), version_id=document_id
                )

        parsed = await asyncio.wait_for(asyncio.to_thread(parse), timeout=timeout)
        chunks = chunk_document(parsed)
        embedding_model = embeddings or make_dashscope_embeddings(
            dimensions=EMBEDDING_DIMENSIONS, timeout=30, max_retries=0
        )
        vectors = validate_vectors(
            await asyncio.wait_for(
                asyncio.to_thread(
                    embedding_model.embed_documents, [c["chunk_text"] for c in chunks]
                ),
                timeout=timeout,
            ),
            len(chunks),
        )
        model_name = dashscope_model_name()
        async with factory() as session, session.begin():
            model = await session.scalar(
                select(Document).where(Document.id == document_id).with_for_update()
            )
            if (
                model is None
                or model.generation != generation
                or model.status != "processing"
            ):
                return  # Deleted/requeued while the network call ran; never resurrect the old job.
            await session.execute(delete(Chunk).where(Chunk.document_id == document_id))
            session.add_all(
                [
                    Chunk(
                        id=uuid5(
                            document_id,
                            f'{document_version}:{generation}:{c["sequence"]}:{hashlib.sha256(c["chunk_text"].encode()).hexdigest()}',
                        ),
                        document_id=document_id,
                        user_id=owner_id,
                        document_version=document_version,
                        generation=generation,
                        embedding=vector,
                        embedding_model=model_name,
                        **c,
                    )
                    for c, vector in zip(chunks, vectors)
                ]
            )
            await session.flush()
            model.status, model.error, model.chunk_count = "ready", None, len(chunks)
            model.page_count, model.embedding_model = parsed.page_count, model_name
    except Exception as exc:
        if not claimed:
            raise
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            else "知识库解析或 Embedding 失败，请检查存储及模型配置后重试"
        )
        async with factory() as session, session.begin():
            await session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.generation == generation,
                    Document.status == "processing",
                )
                .values(status="failed", error=message[:1000])
            )


async def finish_document_delete(
    document_id: UUID, generation: int, *, factory=None, storage=None
):
    factory, storage = factory or SessionLocal, storage or OssObjectStorage()
    async with factory() as session, session.begin():
        model = await session.get(Document, document_id)
        if (
            model is None
            or model.status != "deleting"
            or model.generation != generation
        ):
            return
        key = model.source_key
    try:
        await asyncio.to_thread(storage.delete, key)
    except Exception:
        async with factory() as session, session.begin():
            await session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.status == "deleting",
                    Document.generation == generation,
                )
                .values(error="OSS 原件清理失败，请重试删除；检索索引已撤下")
            )
        return
    async with factory() as session, session.begin():
        await session.execute(
            update(Document)
            .where(
                Document.id == document_id,
                Document.status == "deleting",
                Document.generation == generation,
            )
            .values(status="deleted", error=None, chunk_count=0)
        )
