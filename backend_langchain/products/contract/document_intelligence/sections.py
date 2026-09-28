from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence

from pydantic import ValidationError

from products.contract.domain.document import DocumentBlock, DocumentSection
from products.contract.schemas.document import SectionExtraction

MAX_WINDOW_CHARS = 12000
MAX_WINDOW_BLOCKS = 40
TITLE = re.compile(
    r"^(?:第[一二三四五六七八九十百零〇两\d]+[条章节]|"
    r"[一二三四五六七八九十百]+[、．.]|"
    r"\d+(?:\.\d+)+(?:[、．.)]|\s|$)|\d+[、．.)](?:\s|[^\d]|$)|\d+\s+\S)"
)


def block_windows(blocks: Sequence[DocumentBlock]) -> list[tuple[DocumentBlock, ...]]:
    windows, current, size = [], [], 0
    for block in blocks:
        cost = len(block.text) + 100  # allow for identifier / sequence serialization
        if cost > MAX_WINDOW_CHARS:
            raise ValueError("单个文档 Block 超出局部提取窗口，未截断正文")
        if current and (size + cost > MAX_WINDOW_CHARS or len(current) >= MAX_WINDOW_BLOCKS):
            windows.append(tuple(current))
            current, size = [], 0
        current.append(block)
        size += cost
    if current:
        windows.append(tuple(current))
    return windows


async def detect_sections(
    blocks: Sequence[DocumentBlock],
    fallback: Callable[[Sequence[DocumentBlock]], Awaitable[SectionExtraction]],
) -> tuple[DocumentSection, ...]:
    if not blocks:
        raise ValueError("无法对空文档分段")
    boundaries = [i for i, b in enumerate(blocks)
                  if b.type == "heading" or (b.type != "table" and TITLE.match(b.text.strip()))]
    if boundaries:
        if boundaries[0] != 0:
            boundaries.insert(0, 0)
        sections = []
        for start, end in zip(boundaries, boundaries[1:] + [len(blocks)]):
            title = blocks[start].text[:255]
            for window in block_windows(blocks[start:end]):
                sections.append(DocumentSection(title, tuple(b.block_id for b in window)))
        return tuple(sections)

    # No reliable heading: classify bounded, contiguous windows; never ask for rewritten text.
    sections = []
    for window in block_windows(blocks):
        error = None
        for _ in range(2):
            try:
                result = SectionExtraction.model_validate(await fallback(window))
                ids = [key for section in result.sections for key in section.source_block_ids]
                if ids != [b.block_id for b in window]:
                    raise ValueError("Section 边界必须按顺序完整覆盖窗口，不能重复或编造 Block")
                sections.extend(DocumentSection(s.title, tuple(s.source_block_ids)) for s in result.sections)
                break
            except (ValueError, ValidationError) as exc:
                error = exc
        else:
            raise ValueError(f"Document Intelligence Section 校验失败: {error}") from error
    return tuple(sections)
