"""Parse ordered source blocks once; retain full text for Review V1."""
import hashlib
from io import BytesIO
from uuid import UUID, NAMESPACE_URL, uuid5
from zipfile import ZipFile, BadZipFile

from products.contract.domain.document import DocumentBlock, ParsedDocument, PARSER_VERSION

MAX_BYTES = 20 * 1024 * 1024
MAX_CHARS = 80000
MAX_BLOCK_CHARS = 10000


def validate_file(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit('.', 1)[-1]
    if not data or len(data) > MAX_BYTES:
        raise ValueError('文件为空或超过 20 MB')
    if suffix == 'pdf' and data.startswith(b'%PDF-'):
        return suffix
    if suffix == 'docx':
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError('DOCX 解压后过大')
                if 'word/document.xml' in archive.namelist():
                    return suffix
        except BadZipFile:
            pass
    raise ValueError('请上传有效的 PDF 或 DOCX 文件')


def parse_contract(filename: str, data: bytes, *, version_id: UUID | None = None) -> ParsedDocument:
    kind = validate_file(filename, data)
    # Pure parser calls also have deterministic IDs; production always supplies Version ID.
    version_id = version_id or uuid5(NAMESPACE_URL, hashlib.sha256(data).hexdigest())
    blocks: list[DocumentBlock] = []

    def append(value: str, block_type="paragraph", page=None):
        if value.strip():
            # A very long paragraph/table remains lossless while fitting local LLM windows.
            # Do not strip, normalize, or discard any characters in these source slices.
            for start in range(0, len(value), MAX_BLOCK_CHARS):
                piece = value[start:start + MAX_BLOCK_CHARS]
                sequence = len(blocks) + 1
                block_id = uuid5(version_id, f"{PARSER_VERSION}:{sequence}:{page}:{block_type}:{piece}")
                blocks.append(DocumentBlock(block_id, version_id, sequence, piece, block_type, page))

    if kind == 'pdf':
        import pdfplumber
        from pdfplumber.utils.exceptions import PdfminerException
        from pdfminer.pdfexceptions import PDFException
        try:
            with pdfplumber.open(BytesIO(data)) as pdf:
                page_count = len(pdf.pages)
                if page_count > 100:
                    raise ValueError('Demo 支持最多 100 页合同')
                pages = []
                for number, page in enumerate(pdf.pages, 1):
                    value = page.extract_text() or ""
                    pages.append(f'[第 {number} 页]\n{value}')
                    # Text PDF line order comes from pdfplumber; no invented layout metadata.
                    for line in value.splitlines():
                        append(line, page=number)
                text = '\n\n'.join(pages)
        except (PDFException, PdfminerException, OSError, TypeError) as exc:
            raise ValueError('无法解析 PDF 文件') from exc
        if not blocks:
            raise ValueError('未提取到文字；扫描件暂不支持，请上传文字版 PDF 或 DOCX')
    else:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
        from lxml.etree import XMLSyntaxError
        try:
            document = Document(BytesIO(data))
            for element in document.element.body:
                if element.tag == qn('w:p'):
                    paragraph = Paragraph(element, document)
                    style = paragraph.style.name if paragraph.style else ""
                    append(paragraph.text, "heading" if style.startswith(('Heading', '标题')) else "paragraph")
                elif element.tag == qn('w:tbl'):
                    # Cell tabs and row newlines are an explicit deterministic table serialization.
                    # Walk physical XML cells: python-docx row.cells repeats merged cells.
                    append('\n'.join('\t'.join(
                        '\n'.join(Paragraph(p, document).text for p in cell.iter(qn('w:p')))
                        for cell in row.findall(qn('w:tc'))
                    ) for row in element.findall(qn('w:tr'))), 'table')
        except (BadZipFile, KeyError, ValueError, XMLSyntaxError) as exc:
            raise ValueError('无法解析 DOCX 文件') from exc
        page_count = None  # DOCX has no trustworthy pagination without a layout engine.
        text = '\n\n'.join(f'[段落 {b.sequence}] {b.text}' for b in blocks)
    if not text.strip():
        raise ValueError('文档没有可分析的文字')
    if len(text) > MAX_CHARS:
        raise ValueError('Demo 支持最多 8 万字符，请拆分合同后上传；未进行截断分析')
    return ParsedDocument(version_id, text, tuple(blocks), page_count,
                          'pdfplumber' if kind == 'pdf' else 'python-docx')
